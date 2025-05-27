# repo-main/clients/line_client.py

import os
import logging
import requests # 新增導入 requests
from linebot import LineBotApi
from linebot.models import (
    TextSendMessage,
    FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from config import Config # 導入 Config 以獲取 LINE Token
from utils.error_handler import LineClientError # 導入自定義錯誤

# 獲取日誌記錄器
logger = logging.getLogger(__name__)

# 定義 Quick Reply 按鈕 (全局可用)
COMMON_QR = QuickReply(items=[
    # QuickReplyButton(action=MessageAction(label="使用 OpenAI", text="使用 OpenAI")),
    # QuickReplyButton(action=MessageAction(label="使用 Gemini", text="使用 Gemini")),
    QuickReplyButton(action=MessageAction(label="下一段偵測", text="下一段偵測")),
    QuickReplyButton(action=MessageAction(label="聊聊更多", text="聊聊更多")),
    QuickReplyButton(action=MessageAction(label="分析圖片風險", text="分析圖片風險"))
])

class LineClient:
    """
    負責與 LINE Messaging API 互動的客戶端。
    """
    def __init__(self, channel_access_token: str):
        if not channel_access_token:
            raise LineClientError("CHANNEL_ACCESS_TOKEN 未設定。") # 修改為 CHANNEL_ACCESS_TOKEN
        self.line_bot_api = LineBotApi(channel_access_token)
        logger.info("LineClient 初始化成功。")

    def reply_text(self, reply_token: str, text: str):
        """
        回覆純文字訊息給 LINE 用戶。
        """
        try:
            msg = TextSendMessage(text=text, quick_reply=COMMON_QR)
            self.line_bot_api.reply_message(reply_token, msg)
            logger.info(f"成功回覆文字訊息: '{text[:30]}...'")
        except Exception as e:
            logger.error(f"回覆文字訊息失敗: {e}", exc_info=True)
            raise LineClientError(f"回覆文字訊息失敗。", original_error=e)

    def reply_flex(self, reply_token: str, flex_message_object: FlexSendMessage):
        """
        回覆 Flex Message 給 LINE 用戶。
        """
        try:
            self.line_bot_api.reply_message(reply_token, flex_message_object)
            logger.info(f"成功回覆 Flex Message: '{flex_message_object.alt_text}'")
        except Exception as e:
            logger.error(f"回覆 Flex Message 失敗: {e}", exc_info=True)
            raise LineClientError(f"回覆 Flex Message 失敗。", original_error=e)

    def get_user_profile(self, user_id: str) -> dict:
        """
        從 LINE 獲取用戶的公開資料。
        """
        try:
            url = f"https://api.line.me/v2/bot/profile/{user_id}"
            headers = {
                "Authorization": f"Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}"
            }
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                logger.debug(f"成功獲取用戶 {user_id} 的資料。")
                return res.json()
            else:
                logger.warning(f"取得使用者 {user_id} 資料失敗，狀態碼：{res.status_code}, 內容: {res.text}")
        except Exception as e:
            logger.error(f"[get_user_profile 錯誤]：{e}", exc_info=True)
        return {}
