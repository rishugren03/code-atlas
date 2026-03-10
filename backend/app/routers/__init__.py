from app.routers.health import router as health_router
from app.routers.repos import router as repos_router
from app.routers.ws import router as ws_router

__all__ = ["health_router", "repos_router", "ws_router"]
