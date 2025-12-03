import os

class Settings:
    def __init__(self) -> None:
        # Базовые настройки, при необходимости расширим
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.debug = os.getenv("DEBUG", "0") in ("1", "true", "True")
        # Резерв на будущее: ключи/адреса провайдеров
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = os.getenv("AI_MODEL_NAME", "local-dummy")

settings = Settings()
