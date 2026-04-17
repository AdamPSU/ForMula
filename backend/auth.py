"""Supabase JWT verification for FastAPI (asymmetric keys via JWKS).

Supabase signs user JWTs with ES256/RS256 and publishes the public keys at
`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. PyJWKClient fetches and caches
them; `get_signing_key_from_jwt` picks the right key by `kid`.
"""

from __future__ import annotations

import os
from uuid import UUID

import certifi
import jwt
from fastapi import Header, HTTPException, status

# PyJWKClient fetches via stdlib urllib, which on macOS/uv-managed Python can't
# find a trusted CA bundle. Point stdlib ssl at certifi's bundle before the
# first HTTPS call.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

_ALGORITHMS = ["ES256", "RS256"]
_AUDIENCE = "authenticated"

_jwks_client: jwt.PyJWKClient | None = None


def _client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        base = os.environ["SUPABASE_URL"].rstrip("/")
        _jwks_client = jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def require_user(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        key = _client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=_ALGORITHMS,
            audience=_AUDIENCE,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}")
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing sub")
    try:
        return UUID(sub)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sub is not a uuid")
