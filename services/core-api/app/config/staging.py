from .base import BaseConfig


class StagingConfig(BaseConfig):
    env: str = "staging"
