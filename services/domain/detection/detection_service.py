import logging
import re
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
from config import Config
from utils.error_handler import DetectionError


logger = logging.getLogger(__name__)

# 詐騙訊息關鍵字規則
SCAM_PATTERNS = [
    (re.compile(r"醫(藥)?費|醫療|急需|救急"), "crisis"),
    (re.compile(r"帳戶(被)?凍結"), "crisis"),
    (re.compile(r"(轉|匯|借)[^\d]{0,3}(\d{3,})(元|塊|台幣)"), "payment"),
    (re.compile(r"這是.*帳[戶號]"), "payment"),
]

# LLM Prompt
SYSTEM_PROMPT = """
你是一個詐騙對話階段分類助手。

[Stage definitions]
0 Discovery: 發現目標。初步接觸和簡單交流，獲取基本資訊。
1 Bonding/Grooming: 建立信任和情感連結。透過共同點或浪漫關係拉近距離。
2 Testing Trust: 測試信任程度。可能提出小請求，觀察受害者反應。
3 Crisis Story: 製造危機和緊急情況。通常涉及醫療、法律或財務問題，以激發受害者同情或恐懼。
4 Payment Coaching: 引導付款。提供具體轉帳方式、帳戶資訊或要求購買禮物卡。
5 Aftermath/Repeat: 詐騙成功或失敗後的處理。可能要求更多金錢，或消失、重啟新詐騙。

[判斷依據摘要 - 來自 IEEE 研究]
1. 詐騙者會建立「夢中情人」形象與受害者發展關係（grooming phase），使用甜言蜜語與相似經驗建立信任。
2. 建立關係後，詐騙者會進行信任測試，提出小型請求或私密對話以觀察順從度。
3. 接著常透過醫療費、意外、法律問題等危機情境，激發同情與金錢援助意願。
4. 若受害者願意提供協助，詐騙者會開始具體引導付款流程（帳戶、轉帳、禮物卡等）。
5. 即使付款完成，也可能因「新問題」重複索取或換帳號再犯，稱為 re-victimization。
— 依據《Investigating Online Dating Fraud: An Extensive Review and Analysis》（IEEE 2022）

[輸出格式]
{"stage": <int>, "labels": ["urgency","crisis"]}

[Examples]
<dialog>
User: 嗨～可以認識你嗎？我也住台北！
Assistant: {"stage":1,"labels":["similarity","romance"]}
</dialog>
<dialog>
User: 我急需 5000 付媽媽醫藥費…拜託你幫我！
Assistant: {"stage":3,"labels":["urgency","crisis"]}
</dialog>
<dialog>
User: 這是銀行帳號 000-123-456，現在轉過去就能解凍！
Assistant: {"stage":4,"labels":["payment","urgency"]}
</dialog>
"""

LLM_IMAGE_CHECK_PROMPT = """
你是一個詐騙偵測專家。使用者上傳了一張圖片，圖片內容經模型分析後顯示以下特徵：

[特徵摘要]
- 詐騙類型：{scam_type}
- 檢測特徵：{elements}
- 系統置信度：{confidence:.1%}

請判斷此圖片是否可能與詐騙行為有關，並以 JSON 格式回覆：
{{
  "is_scam": true 或 false,
  "reason": "簡短理由"
}}
"""


RULES = {
    "authority":  ["officer", "bank", "agent", "official", "protocol"],
    "similarity": ["me too", "same", "also", "just like you"],
    "scarcity":   ["last chance", "only today", "limited", "rare"],
    "urgency":    ["urgent", "immediately", "asap", "now", "right away", "快點", "馬上", "立刻"],
    "romance":    ["sweetheart", "my love", "miss you", "never felt", "親愛的", "想你", "寶貝"],
    "crisis":     ["hospital", "surgery", "accident", "fees", "visa", "customs", "醫院", "急診", "手術", "車禍"],
    "payment":    ["transfer", "wire", "crypto", "bitcoin", "gift card", "account number", "匯款", "轉帳", "帳號", "比特幣", "禮物卡"]
}

STAGE_INFO = {
    0: ("關係建立期", "暫無異常，保持正常互動"),
    1: ("情感操控期", "對方正在加速拉近距離，可嘗試要求視訊驗證"),
    2: ("信任測試期", "可能開始測試你的服從度，避免透露隱私/證件"),
    3: ("危機敘事期", "進入情緒勒索，先暫停匯款並與親友討論"),
    4: ("付款引導期", "金錢索求已出現，建議立即停止匯款並求助 165"),
    5: ("重複索求期", "高度疑似詐騙，蒐證後報警"),
}

LABEL_DESC = {
    "crisis":   ("情緒觸發：恐懼/同情",   "白騎士情境、醫療急需等危機敘事"),
    "payment":  ("經濟榨取：金錢索求", "提供帳戶或要求匯款"),
    "urgency":  ("認知偏誤：稀缺/緊迫", "出現『快點』『立刻』等字眼"),
    "authority":("認知偏誤：權威依從", "冒充政府/銀行增加可信度"),
    "similarity":("認知偏誤：同理心", "用相同特徵拉近關係"),
    "romance":  ("情感操控：建立親密感", "使用親暱稱呼、甜言蜜語"),
    "scarcity": ("認知偏誤：稀缺/緊迫", "強調機會難得，錯過不再有"),
    "無異常":   ("無", "未偵測到明確的詐騙特徵")
}

class DetectionService:
    def __init__(self, analysis_client: Optional[Any] = None):
        self.analysis_client = analysis_client
        self.openai_client = self._init_openai_client()

    def _init_openai_client(self) -> Optional[OpenAI]:
        if not Config.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY 未設定，LLM 功能將無法使用。")
            return None
        try:
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info("OpenAI 客戶端初始化成功。")
            return client
        except Exception as e:
            logger.error(f"初始化 OpenAI 客戶端失敗：{e}", exc_info=True)
            return None

    def _match_with_rules(self, text: str) -> List[str]:
        return [label for pattern, label in SCAM_PATTERNS if pattern.search(text)]

    def _classify_with_llm(self, text: str, timeout: int = 5) -> Dict[str, Any]:
        if not self.openai_client:
            return {"stage": 0, "labels": ["LLM_UNAVAILABLE"]}
        try:
            rsp = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                timeout=timeout
            )
            content = rsp.choices[0].message.content
            return json.loads(content) if isinstance(content, str) else content
        except Exception as e:
            logger.error(f"LLM 分類失敗：{e}", exc_info=True)
            return {"stage": 0, "labels": ["LLM_ERROR"], "error_message": str(e)}

    def _infer_stage(self, labels: List[str]) -> int:
        counts = {key: 0 for key in RULES}
        for label in labels:
            if label in counts:
                counts[label] += 1
        if counts["payment"] >= 1: return 4
        if counts["crisis"] >= 1: return 3
        return 0

    def analyze_message(self, message_text: str) -> Dict[str, Any]:
        try:
            labels = self._match_with_rules(message_text)
            if labels:
                stage = self._infer_stage(labels)
                logger.info(f"[規則匹配] Stage={stage}, Labels={labels}")
                return {"stage": stage, "labels": labels}

            llm_result = self._classify_with_llm(message_text)
            stage = llm_result.get("stage", 0)
            labels = llm_result.get("labels", [])
            result = {"stage": stage, "labels": labels}
            if "error_message" in llm_result:
                result["llm_error"] = True
                result["error_message"] = llm_result["error_message"]
                logger.warning(f"[LLM 錯誤] {llm_result['error_message']}")
            else:
                logger.info(f"[LLM 分類] Stage={stage}, Labels={labels}")
            return result
        except Exception as e:
            logger.error(f"[分析錯誤] {e}", exc_info=True)
            return {"stage": 0, "labels": ["分析失敗"], "error": "未知錯誤"}

    def assess_image_risk_with_llm(self, analysis_result: dict) -> dict:
            if not self.openai_client:
                return {"is_scam": False, "reason": "LLM 功能無法使用。"}
            try:
                scam_type = analysis_result["details"].get("scam_type", "未知")
                elements = ", ".join(analysis_result["details"].get("detected_elements", []))
                confidence = analysis_result.get("confidence", 0.0)
                prompt = LLM_IMAGE_CHECK_PROMPT.format(
                    scam_type=scam_type,
                    elements=elements,
                    confidence=confidence
                )
                rsp = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}]
                )
                content = rsp.choices[0].message.content
                return json.loads(content) if isinstance(content, str) else content
            except Exception as e:
                logger.error(f"LLM 圖片風險評估失敗：{e}", exc_info=True)
                return {"is_scam": False, "reason": "無法完成評估"}


    def get_stage_info(self, stage_num: int) -> tuple:
        return STAGE_INFO.get(stage_num, ("未知階段", "請留意對話內容"))

    def get_label_desc(self, label: str) -> tuple:
        return LABEL_DESC.get(label, (label, ""))

    def is_llm_available(self) -> bool:
        return self.openai_client is not None
