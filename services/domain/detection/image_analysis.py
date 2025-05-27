import base64
import os
import json
from openai import OpenAI
from config import Config
from datetime import datetime
import logging

client = OpenAI(api_key=Config.OPENAI_API_KEY)

logger = logging.getLogger(__name__)

def analyze_image(image_path: str) -> dict:
    """
    使用 OpenAI Vision 模型讀取圖片內容並進行詐騙風險分析。
    回傳格式與原先一致。
    """
    if not os.path.exists(image_path):
        return {"is_scam": False, "confidence": 0.0, "details": {"scam_type": "unknown", "detected_elements": [], "risk_level": "low"}}

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "這張圖片可能用於詐騙對話或廣告。\n"
            "請根據圖片內容判斷：\n"
            "1. 是否可能與詐騙有關（例如投資、高報酬、釣魚資訊）？\n"
            "2. 詐騙類型（investment_scam、phishing_scam 等）\n"
            "3. 可疑元素（如高報酬、個資請求、虛假圖表等）\n"
            "請以以下 JSON 格式回覆：\n"
            "{\n  \"is_scam\": true 或 false,\n  \"confidence\": 0.0 ~ 1.0,\n  \"details\": {\n    \"scam_type\": \"\",\n    \"detected_elements\": [],\n    \"risk_level\": \"low/medium/high\"\n  }\n}"
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        result = json.loads(content) if isinstance(content, str) else content

        # 補充時間戳
        result.setdefault("details", {}).update({
            "analysis_time": datetime.now().isoformat()
        })
        return result

    except Exception as e:
        logger.error(f"LLM 圖片分析失敗：{e}", exc_info=True)
        return {"is_scam": False, "confidence": 0.0, "details": {"scam_type": "unknown", "detected_elements": [], "risk_level": "low"}}
