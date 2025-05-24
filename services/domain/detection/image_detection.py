import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ImageDetectionService:
    """
    圖片詐騙分析服務，負責分析圖片內容並產生警示訊息。
    """
    def __init__(self, storage_dir: str = "scam_images"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def analyze_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        分析圖片內容，模擬詐騙偵測。
        Args:
            image_path (str): 圖片檔案路徑
        Returns:
            dict: 分析結果
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"圖片檔案不存在：{image_path}")
                return None
            file_size = os.path.getsize(image_path)
            current_hour = datetime.now().hour
            current_minute = datetime.now().minute
            if file_size < 100000:
                scam_type = "low_quality_scam"
                confidence = 0.6
                risk_level = "medium"
                elements = ["blurry_image", "low_resolution"]
            elif current_hour % 2 == 0:
                scam_type = "investment_scam"
                confidence = 0.85
                risk_level = "high"
                elements = ["fake_investment", "urgency", "high_returns"]
            else:
                scam_type = "phishing_scam"
                confidence = 0.75
                risk_level = "high"
                elements = ["fake_website", "personal_info", "urgency"]
            confidence = min(0.95, confidence + (current_minute / 100))
            analysis_result = {
                "is_scam": True,
                "confidence": confidence,
                "details": {
                    "scam_type": scam_type,
                    "risk_level": risk_level,
                    "detected_elements": elements,
                    "image_size": file_size,
                    "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            logger.info(f"圖片分析完成：{image_path}")
            logger.info(f"分析結果：{json.dumps(analysis_result, ensure_ascii=False)}")
            return analysis_result
        except Exception as e:
            logger.error(f"分析圖片時發生錯誤：{str(e)}")
            return None

    def generate_image_warning(self, analysis_result: dict) -> str:
        """
        根據分析結果產生警示訊息。
        Args:
            analysis_result (dict): 圖片分析結果
        Returns:
            str: 警示訊息
        """
        if not analysis_result:
            return "無法分析圖片內容，請提高警覺。"
        confidence = analysis_result.get("confidence", 0) * 100
        scam_type = analysis_result.get("details", {}).get("scam_type", "未知類型")
        risk_level = analysis_result.get("details", {}).get("risk_level", "未知")
        elements = analysis_result.get("details", {}).get("detected_elements", [])
        scam_type_messages = {
            "investment_scam": "這可能是投資詐騙，請注意：\n1. 不要相信高報酬承諾\n2. 不要輕易投資不熟悉的項目\n3. 不要提供銀行帳戶資訊",
            "phishing_scam": "這可能是釣魚詐騙，請注意：\n1. 不要點擊可疑連結\n2. 不要輸入個人資料\n3. 不要提供密碼或驗證碼",
            "low_quality_scam": "這可能是低品質詐騙，請注意：\n1. 圖片品質不佳可能是偽造的\n2. 不要相信來源不明的圖片\n3. 請向官方管道求證"
        }
        warning_msg = f"""
[警示] 圖片分析結果：
- 詐騙可能性：{confidence:.1f}%
- 詐騙類型：{scam_type}
- 風險等級：{risk_level}
- 檢測到的特徵：{', '.join(elements)}

{scam_type_messages.get(scam_type, '請提高警覺，不要輕易相信可疑訊息。')}

如有疑慮請撥打 165 反詐騙專線
"""
        return warning_msg

    def cleanup_image(self, image_path: str) -> None:
        """
        刪除本地圖片檔案。
        Args:
            image_path (str): 圖片檔案路徑
        """
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
                logger.info(f"已刪除圖片：{image_path}")
        except Exception as e:
            logger.error(f"清理圖片時發生錯誤：{str(e)}") 