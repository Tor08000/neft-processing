from .auth import router as auth_router
from .health import router as health_router
from .processing import router as processing_router

__all__ = ["auth_router", "health_router", "processing_router"]
