import os
from typing import Any

import httpx
from cachetools import TTLCache
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

SUPABASE_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
JWT_AUDIENCE = "authenticated"

# Single-key cache. The JWKS endpoint sets Cache-Control max-age=600 upstream;
# 1h here keeps us comfortably under any plausible key rotation cadence.
_jwks_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1, ttl=3600)


async def _get_jwks() -> dict[str, Any]:
    cached = _jwks_cache.get("jwks")
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(JWKS_URL)
        resp.raise_for_status()
    jwks = resp.json()
    _jwks_cache["jwks"] = jwks
    return jwks


async def get_current_user_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "missing bearer token"
        )
    token = authorization.removeprefix("Bearer ").strip()

    jwks = await _get_jwks()
    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            audience=JWT_AUDIENCE,
        )
    except JWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}"
        ) from e

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "token missing sub claim"
        )
    return sub
