from .routes import router as admin_router
from .partner import router as partner_router

__all__ = ["admin_router", "partner_router"]
