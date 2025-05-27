import os
import requests
import logging
import uuid
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

# 儲存圖片的資料夾
IMAGE_STORAGE_DIR = "scam_images"
os.makedirs(IMAGE_STORAGE_DIR, exist_ok=True)

def handle_image_message(message_id: str, user_id: str) -> str:
    """
    從 LINE 伺服器取得圖片並儲存本地，回傳圖片路徑。
    若下載失敗則回傳 None。
    """
    try:
        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        headers = {
            "Authorization": f"Bearer {Config.LINE_CHANNEL_ACCESS_TOKEN}"
        }

        response = requests.get(url, headers=headers, stream=True)
        if response.status_code != 200:
            logger.error(f"無法取得圖片，狀態碼: {response.status_code}")
            return None

        # 產生唯一檔名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(IMAGE_STORAGE_DIR, filename)

        # 儲存圖片
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        if os.path.getsize(filepath) == 0:
            logger.warning("下載的圖片大小為 0 bytes")
            return None

        logger.info(f"圖片儲存成功：{filepath}")
        return filepath

    except Exception as e:
        logger.error(f"處理圖片訊息時發生錯誤：{e}", exc_info=True)
        return None
