# repo-main/bot/line_webhook.py

import logging
import json
import hmac, hashlib, base64
import time
from flask import Blueprint, request, abort
from linebot.exceptions import InvalidSignatureError
from services.conversation_service import ConversationService # 導入對話服務
from config import Config # 導入 Config 獲取 CHANNEL_SECRET

logger = logging.getLogger(__name__)

# 創建一個 Flask 藍圖
line_webhook = Blueprint("line_webhook", __name__)

# 用於儲存已處理的 Webhook 事件 ID，防止重複處理
PROCESSED_EVENTS = {}
EVENT_ID_LIFETIME = 60 # seconds

class LineWebhookHandler:
    """
    處理 LINE Webhook 事件的類別。
    """
    def __init__(self, conversation_service: ConversationService, channel_secret: str):
        self.conversation_service = conversation_service
        self.channel_secret = channel_secret
        logger.info("LineWebhookHandler 初始化成功。")

    def handle_webhook_event(self, body: str, signature: str):
        """
        處理單個 Webhook 事件。
        """
        # --- Line Signature 驗證 ---
        # 這是確保請求來自 LINE 的安全措施
        hash_bytes = hmac.new(self.channel_secret.encode(), body.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(base64.b64encode(hash_bytes).decode(), signature):
            logger.warning("Line Signature 驗證失敗。請求可能來自未授權來源。")
            raise InvalidSignatureError("Invalid signature")

        event_data = json.loads(body)
        logger.info(f"\n==== [Log] 接收到的 Line Webhook 資料 ====\n{json.dumps(event_data, ensure_ascii=False, indent=2)}")

        events = event_data.get("events", [])

        # --- Webhook 事件去重 ---
        # 清理過期的事件 ID
        current_time = time.time()
        global PROCESSED_EVENTS # 聲明為全局變數
        PROCESSED_EVENTS = {event_id: timestamp for event_id, timestamp in PROCESSED_EVENTS.items() if current_time - timestamp < EVENT_ID_LIFETIME}

        for ev in events:
            event_id = ev.get("webhookEventId")
            is_redelivery = ev.get("deliveryContext", {}).get("isRedelivery", False)

            if event_id and event_id in PROCESSED_EVENTS and is_redelivery:
                logger.info(f"重複的 Webhook 事件 ID: {event_id} (isRedelivery: {is_redelivery}). 跳過處理。")
                continue

            if event_id:
                PROCESSED_EVENTS[event_id] = current_time

            user_id = ev["source"]["userId"]
            reply_token = ev.get("replyToken")

            # --- 處理 Postback 事件 ---
            if ev["type"] == "postback":
                self.conversation_service.handle_postback(user_id, ev["postback"]["data"], reply_token)
            # --- 處理文字訊息事件 ---
            elif ev["type"] == "message" and ev["message"]["type"] == "text":
                self.conversation_service.handle_message(user_id, ev["message"]["text"], reply_token)
            # --- 處理圖片訊息事件 ---
            elif ev["type"] == "message" and ev["message"]["type"] == "image":
                self.conversation_service.handle_image_message(user_id, ev["message"]["id"], reply_token)
            # 可以添加其他事件類型 (如影片等) 的處理

# 在藍圖中定義 Webhook 路由
@line_webhook.route("/callback", methods=["POST"])
def callback():
    """
    LINE Webhook 的主要入口點。
    """
    # 獲取簽名和請求體
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    # 獲取 LineWebhookHandler 實例 (由 app.py 在 create_app 中設定)
    handler: LineWebhookHandler = line_webhook.webhook_handler # type: ignore

    try:
        handler.handle_webhook_event(body, signature)
    except InvalidSignatureError:
        logger.error("Line Signature 驗證失敗。")
        abort(403) # 403 Forbidden
    except Exception as e:
        logger.error(f"處理 Webhook 事件時發生錯誤: {e}", exc_info=True)
        abort(500) # 500 Internal Server Error

    return "OK", 200
