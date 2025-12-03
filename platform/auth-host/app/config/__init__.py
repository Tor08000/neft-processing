from importlib import import_module
from typing import Type

from .base import BaseConfig


def get_config() -> BaseConfig:
    env = BaseConfig().env
    module_name = f"{__name__}.{env}"
    try:
        module = import_module(module_name)
        config_class: Type[BaseConfig] = getattr(module, f"{env.capitalize()}Config")
        return config_class()
    except Exception:
        return BaseConfig()

__all__ = ["get_config", "BaseConfig"]
