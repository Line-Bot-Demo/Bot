from google import genai
import logging
from config import Config

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self,api_key):
        try:
            self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
            self.model = self.client.get_model(name="models/gemini-flash-001")
            logger.info("Gemini Client initialized successfully")
        except Exception as e:
            logger.error(f"init Gemini Client failed: {e}", exc_info=True)
            self.model = None

    def chat(self, prompt: str) -> str:
        if not self.model:
            return "Gemini client did not initialize properly. Please check the logs."
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini response failed: {e}", exc_info=True)
            return "Gemini call failed, please try again later."
