"""Sage Cloud API key authentication middleware."""

import logging

from fastapi import Depends, HTTPException, Query, Request

from sage_cloud.config import Settings, get_settings
from sage_cloud.models import ToolError

logger = logging.getLogger(__name__)


class AuthContext:
    """Holds validated auth information for a request."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __repr__(self) -> str:
        return f"AuthContext(key={self.key[:12]}...)"


async def verify_api_key(
    request: Request,
    key: str | None = Query(default=None, alias="key"),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """
    FastAPI dependency that validates the API key.

    Checks X-Sage-Key header first, then ?key= query param.
    Returns AuthContext on success.
    Raises 401 if no key provided, 403 if key is invalid.

    Development bypass: if SAGE_CLOUD_ENV=development and SAGE_CLOUD_API_KEYS is empty,
    all requests are allowed without a key.
    """
    valid_keys = set(settings.api_keys_list())

    # Development bypass
    if settings.SAGE_CLOUD_ENV == "development" and not valid_keys:
        logger.warning("SAGE_CLOUD: no API keys configured — development bypass active, all requests allowed")
        return AuthContext(key="dev-bypass")

    # Production guard
    if settings.SAGE_CLOUD_ENV == "production" and not valid_keys:
        raise HTTPException(
            status_code=500,
            detail=ToolError(
                error="misconfigured",
                detail="SAGE_CLOUD_API_KEYS must be set in production",
                tool_name="auth",
            ).model_dump(),
        )

    # Resolve key: header takes precedence over query param
    provided_key = request.headers.get("X-Sage-Key") or key

    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail=ToolError(
                error="unauthorized",
                detail="API key required. Provide X-Sage-Key header or ?key= query param.",
                tool_name="auth",
            ).model_dump(),
        )

    if provided_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail=ToolError(
                error="forbidden",
                detail="Invalid API key.",
                tool_name="auth",
            ).model_dump(),
        )

    return AuthContext(key=provided_key)


# Convenience alias for use as FastAPI Depends()
require_auth = Depends(verify_api_key)
