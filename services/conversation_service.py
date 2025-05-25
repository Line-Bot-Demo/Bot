import logging
import json
from typing import Dict, List, Any, Optional
from collections import defaultdict
from openai import OpenAI
from config import Config
from services.domain.detection.detection_service import DetectionService
from clients.line_client import LineClient, COMMON_QR
from linebot.models import FlexSendMessage, QuickReply
from services.domain.detection.image_detection import ImageDetectionService
import tempfile
import requests
import os

logger = logging.getLogger(__name__)

class ConversationService:
    """
    負責管理用戶對話流程、狀態和生成回覆。
    協調檢測服務和 LINE 客戶端。
    """
    def __init__(self, detection_service: DetectionService, line_client: LineClient):
        self.detection_service = detection_service
        self.line_client = line_client

        # 用於儲存每個用戶的當前會話狀態，例如最後的檢測結果
        self.STATE = defaultdict(lambda: {"risk": 0, "money_calls": 0, "last_result": {}})
        # 用於儲存用戶聊天歷史
        self.user_chat_history = defaultdict(list)

        self.openai_client = None
        if Config.OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
                logger.info("ConversationService: OpenAI 客戶端初始化成功。")
            except Exception as e:
                logger.error(f"ConversationService: 初始化 OpenAI 客戶端失敗：{e}", exc_info=True)
                self.openai_client = None
        else:
            logger.warning("ConversationService: OPENAI_API_KEY 未設定，LLM 相關功能將無法使用。")

        self.image_detection_service = ImageDetectionService()

    def handle_message(self, user_id: str, message_text: str, reply_token: str):
        """
        處理接收到的文字訊息。
        """
        logger.info(f"處理訊息: User ID={user_id}, Message='{message_text}'")

        # --- 特殊指令處理：「下一段偵測」---
        if message_text == "下一段偵測":
            self.STATE[user_id]["last_result"] = {} # 重置上一個檢測結果
            self.user_chat_history[user_id].clear() # 清除聊天歷史
            logger.info(f"User {user_id} 重置偵測狀態。")
            reset_bubble_content = {
              "type":"bubble",
              "body":{"type":"box","layout":"vertical","contents":[
                {"type":"text",
                 "text":"📩 請傳送下一段對話，我會重新開始偵測。",
                 "wrap":True, "align":"center"}
              ]}
            }
            self.line_client.reply_flex(reply_token, self._build_flex_message_from_content(
                alt_text="重置偵測", contents=reset_bubble_content, quick_reply=COMMON_QR))
            return

        # --- 特殊指令處理：「聊聊更多」---
        if message_text == "聊聊更多":
            logger.info(f"User {user_id} 請求『聊聊更多』。")
            history = self.user_chat_history.get(user_id, [])
            if not history:
                self.line_client.reply_text(reply_token, "目前沒有聊天紀錄可以延伸喔！")
                return

            if not self.openai_client:
                logger.warning("OpenAI 客戶端未初始化或 API Key 無效，無法提供『聊聊更多』功能。")
                self.line_client.reply_text(reply_token, "抱歉，AI 功能目前無法使用，請檢查 API Key 或配額。")
                return

            prompt_history = "\n".join(history[-5:]) # 只取最近的 5 條訊息
            prompt = "以下是我和對方的對話紀錄：\n" + prompt_history + "\n請基於這些內容，繼續和我聊天。"

            try:
                rsp = self.openai_client.chat.completions.create(
                  model="gpt-4o-mini",
                  messages=[{"role":"user","content":prompt}]
                )
                self.line_client.reply_text(reply_token, rsp.choices[0].message.content)
            except Exception as e:
                logger.error(f"ChatGPT 『聊聊更多』失敗：{e}", exc_info=True)
                self.line_client.reply_text(reply_token, "抱歉，目前無法提供更多對話。請確認 OpenAI API Key 或配額是否正常。")
            return

        # --- 主要訊息分析流程 ---
        self.user_chat_history[user_id].append(message_text) # 儲存當前訊息

        result = self.detection_service.analyze_message(message_text) # 呼叫檢測服務
        self.STATE[user_id]["last_result"] = result # 儲存最近一次結果

        flex_message_to_send = self._build_detection_flex_message(result) # 構建 Flex Message
        self.line_client.reply_flex(reply_token, flex_message_to_send)

    def handle_postback(self, user_id: str, data: str, reply_token: str):
        """
        處理接收到的 Postback 事件。
        """
        logger.info(f"處理 Postback: User ID={user_id}, Data={data}")

        last_result = self.STATE[user_id].get("last_result", {})
        if not last_result or last_result.get("stage") is None:
            logger.warning(f"Postback received but last_result is invalid for user {user_id}. Sending prompt.")
            self.line_client.reply_text(reply_token, "抱歉，請您先傳送一段對話，我才能為您分析並提供判斷依據或防範建議。")
            return

        if data == "action=explain":
            response_text = self._explain_classification(user_id)
            self.line_client.reply_text(reply_token, response_text)
        elif data == "action=prevent":
            response_text = self._prevention_suggestions(user_id)
            self.line_client.reply_text(reply_token, response_text)

    def _explain_classification(self, user_id: str) -> str:
        """
        根據用戶上次的詐騙檢測結果，生成解釋文本。
        """
        if not self.openai_client:
            logger.warning("OpenAI 客戶端未初始化或 API Key 無效，無法提供解釋。")
            return "抱歉，AI 功能目前無法使用，請檢查 API Key 或配額。"

        last = self.STATE[user_id].get("last_result")
        if not last or last.get("stage") is None:
            logger.warning(f"_explain_classification: User {user_id} last_result is invalid or missing stage.")
            return "抱歉，沒有找到上次的檢測結果，無法解釋判斷依據。請先傳送訊息讓我分析。"

        # 確保 stage 在 STAGE_INFO 中存在，否則使用預設值
        stage_num = last.get("stage", 0)
        # 從 detection_service 獲取 stage_name
        stage_name_for_explain = self.detection_service.get_stage_info(stage_num)[0]

        # 組合觸發因子名稱，如果沒有則顯示「無」
        trigger_factors = "、".join([
            self.detection_service.get_label_desc(lab)[0] # 從 detection_service 獲取標籤描述
            for lab in last.get("labels", [])
        ]) or "無"

        prompt = (
          f"我剛剛偵測到一個訊息，分類結果為階段 {stage_num}（{stage_name_for_explain}），"
          f"觸發因子有 {trigger_factors}。"
          "請用 2～3 句話簡單說明為何會做出這樣的判斷。"
        )
        try:
            rsp = self.openai_client.chat.completions.create(
              model="gpt-4o-mini",
              messages=[{"role":"user", "content":prompt}]
            )
            return rsp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"解釋判斷失敗：{e}", exc_info=True)
            return "抱歉，目前無法提供判斷說明。請確認 OpenAI API Key 或配額是否正常。"

    def _prevention_suggestions(self, user_id: str) -> str:
        """
        根據用戶上次的詐騙檢測結果，生成防範建議文本。
        """
        if not self.openai_client:
            logger.warning("OpenAI 客戶端未初始化或 API Key 無效，無法提供防範建議。")
            return "抱歉，AI 功能目前無法使用，請檢查 API Key 或配額。"

        last = self.STATE[user_id].get("last_result")
        if not last or last.get("stage") is None:
            logger.warning(f"_prevention_suggestions: User {user_id} last_result is invalid or missing stage.")
            return "抱歉，沒有找到上次的檢測結果，無法提供防範建議。請先傳送訊息讓我分析。"

        # 確保 stage 在 STAGE_INFO 中存在，否則使用預設值
        stage_num = last.get("stage", 0)
        # 從 detection_service 獲取 stage_name
        stage_name_for_prevent = self.detection_service.get_stage_info(stage_num)[0]

        # 組合觸發因子名稱，如果沒有則顯示「無」
        trigger_factors = "、".join([
            self.detection_service.get_label_desc(lab)[0] # 從 detection_service 獲取標籤描述
            for lab in last.get("labels", [])
        ]) or "無"

        prompt = (
          f"根據詐騙階段 {stage_num}（{stage_name_for_prevent}），"
          f"觸發因子 {trigger_factors}，"
          "請列出 3 條最實用的防範建議。"
        )
        try:
            rsp = self.openai_client.chat.completions.create(
              model="gpt-4o-mini",
              messages=[{"role":"user", "content":prompt}]
            )
            return rsp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"提供防範建議失敗：{e}", exc_info=True)
            return "抱歉，目前無法提供防範建議。請確認 OpenAI API Key 或配額是否正常。"

    def _build_flex_message_from_content(self, alt_text: str, contents: dict, quick_reply: Optional[QuickReply] = None) -> FlexSendMessage:
        """
        輔助函數：從內容字典構建 FlexSendMessage。
        """
        return FlexSendMessage(alt_text=alt_text, contents=contents, quick_reply=quick_reply)

    def _build_detection_flex_message(self, result: dict) -> FlexSendMessage:
        """
        根據詐騙偵測結果，構建並返回一個 LINE Flex Message 物件。
        """
        stage_num = result.get("stage", 0)
        s_name, advice = self.detection_service.get_stage_info(stage_num)

        labels = result.get("labels", [])
        reasons = "、".join(
            f"{self.detection_service.get_label_desc(lab)[0]}"
            for lab in labels if self.detection_service.get_label_desc(lab)
        ) or "無風險標籤"

        # 檢查是否有 LLM 錯誤
        if result.get("llm_error"):
            # 如果 LLM 失敗，修改建議行動和觸發因子顯示
            reasons = "LLM 分析失敗"
            advice = f"AI 功能暫時無法使用。原因：{result.get('error_message', '未知錯誤')}。請檢查 OpenAI 配額或稍後重試。"
            # 也可以考慮改變顏色或添加圖標來表示錯誤
            stage_display = "❌ 分析異常"
            color = "#FF0000"  # 紅色表示錯誤
        else:
            stage_display = f"🔎 目前階段：{stage_num}（{s_name}）"
            color = "#1DB446" if stage_num <= 1 else "#FF0000" if stage_num >= 3 else "#FFBB00"  # 根據階段更改顏色

        bubble_content = {
            "type": "bubble",
            "body": {
                "type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": stage_display, "weight": "bold", "size": "lg", "color": color},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"📌 觸發因子：{reasons}", "wrap": True, "margin": "md"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"👉 建議行動：{advice}", "wrap": True, "margin": "md"}
                ]
            },
            "footer": {
                "type": "box", "layout": "horizontal", "contents": [
                    {"type": "button", "style": "link", "height": "sm",
                     "action": {"type": "postback", "label": "為何這樣判斷？", "data": "action=explain"}},
                    {"type": "button", "style": "link", "height": "sm",
                     "action": {"type": "postback", "label": "如何防範？", "data": "action=prevent"}}
                ]
            }
        }

        return self._build_flex_message_from_content(
            alt_text="詐騙偵測結果", contents=bubble_content, quick_reply=COMMON_QR)

    def handle_image_message(self, user_id: str, message_id: str, reply_token: str):
        """
        處理接收到的圖片訊息。
        """
        logger.info(f"處理圖片訊息: User ID={user_id}, MessageID={message_id}")
        # 1. 下載圖片
        image_path = self._download_image_from_line(message_id, user_id)
        if not image_path:
            self.line_client.reply_text(reply_token, "無法處理圖片，請稍後再試。")
            return
        try:
            # 2. 分析圖片
            analysis_result = self.image_detection_service.analyze_image(image_path)
            # 3. 生成回覆訊息
            if analysis_result and analysis_result.get("is_scam"):
                warning_msg = self.image_detection_service.generate_image_warning(analysis_result)
                self.line_client.reply_text(reply_token, warning_msg)
            else:
                self.line_client.reply_text(reply_token, "圖片分析完成，未發現明顯詐騙跡象，但仍請保持警覺。")
        finally:
            # 4. 清理圖片
            self.image_detection_service.cleanup_image(image_path)

    def _download_image_from_line(self, message_id: str, user_id: str) -> str:
        """
        從 LINE 下載圖片並儲存到本地。
        Returns: 圖片本地路徑，失敗則回傳空字串。
        """
        try:
            url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
            headers = {"Authorization": f"Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}"}
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code == 200:
                temp_dir = self.image_detection_service.storage_dir
                os.makedirs(temp_dir, exist_ok=True)
                filename = f"{user_id}_{message_id}.jpg"
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return filepath
            else:
                logger.error(f"無法獲取圖片，狀態碼：{response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"下載圖片時發生錯誤：{str(e)}")
            return ""
