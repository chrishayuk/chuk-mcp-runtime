# chuk_mcp_runtime/common/verify_credentials.py
"""
JWT-based credential validation for the CHUK MCP runtime.

* Reads secret, allowed algorithms, and leeway from env vars
  - defaults are safe but test-friendly.
* Adds a small leeway so that fractional-second ``exp`` values created
  with ``datetime.utcnow().timestamp()`` don't fail validation by a
  couple of milliseconds.
"""

from __future__ import annotations

import os
from typing import List

import jwt
from jwt import PyJWTError
from jwt.exceptions import ExpiredSignatureError
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

# ---------------------------------------------------------------------------#
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------#
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "my-test-key")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

# Allowed algs - comma-separated env var or sensible default set
_default_algs = f"{JWT_ALGORITHM},HS384,HS512"
JWT_ALLOWED_ALGORITHMS: List[str] = [
    alg.strip()
    for alg in os.getenv("JWT_ALLOWED_ALGORITHMS", _default_algs).split(",")
    if alg.strip()
]

# Leeway in *seconds* to tolerate clock drift / sub-second rounding
JWT_LEEWAY: int = int(os.getenv("JWT_LEEWAY", "1"))


# ---------------------------------------------------------------------------#
# Public API
# ---------------------------------------------------------------------------#
async def validate_token(token: str) -> dict:
    """
    Decode **token** and return its claims dict on success.

    Raises
    ------
    starlette.exceptions.HTTPException
        401 Unauthorized with details “Token has expired” or “Invalid token”.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=JWT_ALLOWED_ALGORITHMS,
            leeway=JWT_LEEWAY,
        )
        # Echo the raw token back so middleware can forward it if needed
        payload["token"] = token
        return payload

    except ExpiredSignatureError:
        # Specific expired-token case
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except PyJWTError:
        # Any other JWT error → generic invalid-token response
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
