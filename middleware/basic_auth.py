import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.status import HTTP_401_UNAUTHORIZED

from core.config import get_settings


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.auth_enabled or request.url.path.startswith("/static"):
            return await call_next(request)

        credentials = request.headers.get("authorization", "")
        if credentials.startswith("Basic "):
            import base64

            try:
                decoded = base64.b64decode(credentials.removeprefix("Basic ")).decode()
                username, password = decoded.split(":", 1)
                valid = secrets.compare_digest(
                    username, settings.auth_username
                ) and secrets.compare_digest(password, settings.auth_password)
                if valid:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            "Authentication required",
            status_code=HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="MongoDB Monitoring"'},
        )
