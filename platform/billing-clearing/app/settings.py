from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for Celery workers."""

    service_name: str = Field(default="workers", alias="SERVICE_NAME")
    broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER_URL")
    result_backend: str = Field(default="redis://redis:6379/1", alias="CELERY_RESULT_BACKEND")
    redis_url: str = Field(default="redis://redis:6379/2", alias="REDIS_URL")
    task_default_queue: str = Field(default="celery", alias="CELERY_DEFAULT_QUEUE")
    worker_max_tasks_per_child: int = Field(
        default=100, alias="CELERY_WORKER_MAX_TASKS_PER_CHILD"
    )
    worker_prefetch_multiplier: int = Field(
        default=1, alias="CELERY_WORKER_PREFETCH_MULTIPLIER"
    )
    task_soft_time_limit: int = Field(default=240, alias="CELERY_TASK_SOFT_TIME_LIMIT")
    task_time_limit: int = Field(default=300, alias="CELERY_TASK_TIME_LIMIT")
    queue_prefix: str = Field(default="neft:celery", alias="CELERY_PREFIX")

    ai_service_url: str = Field(default="http://ai-service:8000", alias="AI_SERVICE_URL")
    core_api_url: str = Field(default="http://core-api:8000", alias="CORE_API_URL")
    http_timeout: float = Field(default=5.0, alias="WORKER_HTTP_TIMEOUT")

    # task defaults
    task_default_retry_delay: int = 15  # seconds
    task_max_retries: int = 5
    visibility_timeout: int = 600  # seconds
    result_expires: int = 3600  # seconds
    timezone: str = "Europe/Moscow"


settings = Settings()
