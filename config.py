import os
from dotenv import load_dotenv

# 載入 .env
load_dotenv()

class Config:
    # LINE Bot API 憑證
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

    # OpenAI API Key（可選）
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Gemini API Key（新增）
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # 外部分析 API URL
    ANALYSIS_API_URL = os.getenv("ANALYSIS_API_URL")

    # Flask 應用程式配置
    PORT = int(os.getenv("PORT", 5080))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # 日誌級別
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # 預設使用哪個模型（可選: "openai" 或 "gemini"）
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai").lower()

    @staticmethod
    def validate():
        if not Config.LINE_CHANNEL_ACCESS_TOKEN:
            raise ValueError("CHANNEL_ACCESS_TOKEN 是必要的")
        if not Config.LINE_CHANNEL_SECRET:
            raise ValueError("CHANNEL_SECRET 是必要的")
        # Gemini 或 OpenAI 任一可用即可
        if not Config.OPENAI_API_KEY and not Config.GEMINI_API_KEY:
            raise ValueError("至少需提供 OPENAI_API_KEY 或 GEMINI_API_KEY")