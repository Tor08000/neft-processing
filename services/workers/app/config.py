from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    queue_prefix: str = Field(default="neft:celery", alias="CELERY_PREFIX")
    # task defaults
    task_default_retry_delay: int = 15   # seconds
    task_max_retries: int = 5
    visibility_timeout: int = 600       # seconds
    result_expires: int = 3600          # seconds
    timezone: str = "Europe/Moscow"

settings = Settings()
