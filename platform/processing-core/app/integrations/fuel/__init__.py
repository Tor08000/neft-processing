"""Fuel integration package.

Keep imports side-effect free to avoid circular dependencies during model import.
"""

from app.integrations.fuel.registry import load_default_providers

__all__ = ["load_default_providers"]
