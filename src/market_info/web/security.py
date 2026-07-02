import hmac
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def is_public_path(path: str) -> bool:
    return path.startswith("/static/") or path == "/favicon.ico"


def is_authorized(headers: Mapping[str, str], token: str) -> bool:
    if not token:
        return True
    authorization = _get_header(headers, "authorization")
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        return False
    provided_token = authorization[len(prefix) :]
    return hmac.compare_digest(provided_token, token)


def install_access_guard(app: FastAPI, token: str) -> None:
    if not token:
        return

    @app.middleware("http")
    async def access_guard(request: Request, call_next):
        if is_public_path(request.url.path) or is_authorized(request.headers, token):
            return await call_next(request)
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    if value is not None:
        return value
    folded = name.lower()
    for key, item in headers.items():
        if key.lower() == folded:
            return item
    return None
