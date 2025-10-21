"""
Test module for verify_credentials.py

Tests JWT token validation and error handling.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest

# Import directly from the file rather than as a module
from chuk_mcp_runtime.common.verify_credentials import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    validate_token,
)
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED


# --- Test fixtures ---
@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "test-user",
        "name": "Test User",
        "role": "admin",
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


@pytest.fixture
def expired_token():
    """Create an expired JWT token for testing."""
    payload = {
        "sub": "test-user",
        "name": "Test User",
        "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


@pytest.fixture
def token_with_expiration():
    """Create a JWT token with expiration set in the future."""
    payload = {
        "sub": "test-user",
        "name": "Test User",
        "role": "admin",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# --- Tests for validate_token ---
@pytest.mark.asyncio
async def test_validate_valid_token(valid_token):
    """Test validating a valid token."""
    # Validate the token
    payload = await validate_token(valid_token)

    # Check that the payload contains expected fields
    assert "sub" in payload
    assert payload["sub"] == "test-user"
    assert "name" in payload
    assert payload["name"] == "Test User"
    assert "role" in payload
    assert payload["role"] == "admin"
    assert "token" in payload
    assert payload["token"] == valid_token


@pytest.mark.asyncio
async def test_validate_token_with_expiration(token_with_expiration):
    """Test validating a token with an expiration time."""
    # Validate the token
    payload = await validate_token(token_with_expiration)

    # Check that the payload contains expected fields
    assert "sub" in payload
    assert "exp" in payload
    assert payload["token"] == token_with_expiration


@pytest.mark.asyncio
async def test_validate_expired_token(expired_token):
    """Test validating an expired token."""
    # Attempt to validate the expired token
    with pytest.raises(HTTPException) as excinfo:
        await validate_token(expired_token)

    # Check that the exception contains the expected details
    assert excinfo.value.status_code == HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Token has expired"
    assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_validate_invalid_token():
    """Test validating an invalid token."""
    # Attempt to validate an invalid token
    with pytest.raises(HTTPException) as excinfo:
        await validate_token("invalid.token.string")

    # Check that the exception contains the expected details
    assert excinfo.value.status_code == HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid token"
    assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_validate_token_wrong_secret():
    """Test validating a token signed with a different secret."""
    # Create a token signed with a different secret
    payload = {"sub": "test-user", "name": "Test User"}
    wrong_token = jwt.encode(payload, "wrong-secret", algorithm=JWT_ALGORITHM)

    # Attempt to validate the token
    with pytest.raises(HTTPException) as excinfo:
        await validate_token(wrong_token)

    # Check that the exception contains the expected details
    assert excinfo.value.status_code == HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid token"
    assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_validate_token_wrong_algorithm():
    """Test validating a token signed with a different algorithm."""
    # Create a token signed with a different algorithm
    payload = {"sub": "test-user", "name": "Test User"}
    wrong_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS512")

    # Payload will still be valid as long as the algorithm is specified in the allowed list
    payload = await validate_token(wrong_token)
    assert payload["sub"] == "test-user"


@pytest.mark.asyncio
async def test_validate_token_with_custom_secret():
    """Test validating a token with a custom secret set in environment."""
    # Save original secret key
    original_secret = JWT_SECRET_KEY

    # Set custom secret via environment variable
    with patch.dict(os.environ, {"JWT_SECRET_KEY": "custom-secret-key"}):
        # Re-import to get the new secret
        import importlib

        import chuk_mcp_runtime.common.verify_credentials

        importlib.reload(chuk_mcp_runtime.common.verify_credentials)
        from chuk_mcp_runtime.common.verify_credentials import (
            validate_token as custom_validate_token,
        )

        # Create a token with the custom secret
        payload = {"sub": "test-user", "name": "Test User"}
        custom_token = jwt.encode(payload, "custom-secret-key", algorithm=JWT_ALGORITHM)

        # Validate the token
        result = await custom_validate_token(custom_token)
        assert result["sub"] == "test-user"

        # Attempt to validate with the original token (should fail)
        original_token = jwt.encode(payload, original_secret, algorithm=JWT_ALGORITHM)
        with pytest.raises(HTTPException):
            await custom_validate_token(original_token)
