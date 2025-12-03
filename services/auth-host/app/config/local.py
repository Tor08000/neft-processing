from .base import BaseConfig


class LocalConfig(BaseConfig):
    enable_tracing: bool = False
    env: str = "local"
