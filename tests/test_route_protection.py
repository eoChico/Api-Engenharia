from fastapi.routing import APIRoute

from app.api.deps import get_current_user
from app.main import app

PUBLIC_PATHS = {
    "/health",
    "/health/db",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}


def _uses(dependant, target) -> bool:
    return any(d.call is target or _uses(d, target) for d in dependant.dependencies)


def test_every_route_requires_auth_unless_public():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC_PATHS:
            assert _uses(route.dependant, get_current_user), f"Rota sem auth: {route.path}"
