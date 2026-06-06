"""Optional API-key auth.

When `Settings.api_key` is set, all `/api/*` routes require
`Authorization: Bearer <key>` and the WebSocket endpoint requires `?token=<key>`
on the URL. When unset, the API is open — appropriate for local dev.

`health` and `ready` always stay open so liveness probes work in any setup.

Why a custom dependency instead of e.g. fastapi-users / fastapi.security:
this is a single-shared-key model intended for single-tenant deployments and
does not need OAuth/JWT/users. A constant-time compare on a SecretStr is the
whole story.
"""
from __future__ import annotations

import hmac

from fastapi import Depends, Header, Query

from app.core.config import Settings, get_settings
from app.core.errors import AppError


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


def _check(provided: str | None, expected: str) -> None:
    if not provided or not hmac.compare_digest(provided, expected):
        raise UnauthorizedError("Invalid or missing API key")


async def require_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency for REST routes."""
    if not settings.auth_required:
        return
    if authorization is None:
        raise UnauthorizedError("Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise UnauthorizedError("Authorization scheme must be Bearer")
    _check(token.strip(), settings.api_key.get_secret_value())


async def require_ws_token(
    token: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency for WebSocket routes."""
    if not settings.auth_required:
        return
    _check(token, settings.api_key.get_secret_value())
