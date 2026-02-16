"""
Маркер пакета services для Core API (бизнес-логика).
"""

# Re-export frequently used service modules for convenient monkeypatching in tests
from app.services import admin_auth  # noqa: F401
from app.services import client_auth  # noqa: F401
