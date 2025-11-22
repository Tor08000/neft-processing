import os
from dataclasses import dataclass

@dataclass
class Settings:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain")

def get_settings() -> Settings:
    return Settings()
