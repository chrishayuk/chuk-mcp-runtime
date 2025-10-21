"""
Tests for request context and progress reporting.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from chuk_mcp_runtime.server.request_context import (
    MCPRequestContext,
    RequestContext,
    get_request_context,
    send_progress,
    set_request_context,
)


@pytest.fixture
def mock_session():
    """Create a mock MCP session with send_progress_notification."""
    session = AsyncMock()
    session.send_progress_notification = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def clear_context():
    """Clear request context before and after each test."""
    set_request_context(None)
    yield
    set_request_context(None)


def test_request_context_init():
    """Test MCPRequestContext initialization."""
    session = Mock()
    ctx = MCPRequestContext(session=session, progress_token="test-token", meta={"key": "value"})

    assert ctx.session is session
    assert ctx.progress_token == "test-token"
    assert ctx.meta == {"key": "value"}


def test_request_context_init_defaults():
    """Test MCPRequestContext initialization with defaults."""
    ctx = MCPRequestContext()

    assert ctx.session is None
    assert ctx.progress_token is None
    assert ctx.meta is None


@pytest.mark.asyncio
async def test_send_progress_with_session_and_token(mock_session):
    """Test sending progress with valid session and token."""
    ctx = MCPRequestContext(session=mock_session, progress_token="test-token")

    await ctx.send_progress(progress=50.0, total=100.0, message="Half done")

    mock_session.send_progress_notification.assert_called_once_with(
        progress_token="test-token", progress=50.0, total=100.0, message="Half done"
    )


@pytest.mark.asyncio
async def test_send_progress_without_session():
    """Test sending progress without a session (should log warning)."""
    ctx = MCPRequestContext(progress_token="test-token")

    # Should not raise, just log warning
    await ctx.send_progress(progress=50.0, total=100.0)


@pytest.mark.asyncio
async def test_send_progress_without_token(mock_session):
    """Test sending progress without a progress token (should skip)."""
    ctx = MCPRequestContext(session=mock_session)

    await ctx.send_progress(progress=50.0, total=100.0)

    # Should not call send_progress_notification
    mock_session.send_progress_notification.assert_not_called()


@pytest.mark.asyncio
async def test_send_progress_optional_params(mock_session):
    """Test sending progress with optional parameters."""
    ctx = MCPRequestContext(session=mock_session, progress_token="test-token")

    # Test with just progress
    await ctx.send_progress(progress=25.0)

    mock_session.send_progress_notification.assert_called_with(
        progress_token="test-token", progress=25.0, total=None, message=None
    )


@pytest.mark.asyncio
async def test_send_progress_with_error(mock_session):
    """Test send_progress handles errors gracefully."""
    mock_session.send_progress_notification.side_effect = Exception("Network error")

    ctx = MCPRequestContext(session=mock_session, progress_token="test-token")

    # Should not raise, just log error
    await ctx.send_progress(progress=50.0)


def test_get_set_request_context():
    """Test getting and setting request context."""
    assert get_request_context() is None

    ctx = MCPRequestContext(progress_token="test-token")
    set_request_context(ctx)

    assert get_request_context() is ctx

    set_request_context(None)
    assert get_request_context() is None


@pytest.mark.asyncio
async def test_send_progress_function_with_context(mock_session):
    """Test global send_progress function with context."""
    ctx = MCPRequestContext(session=mock_session, progress_token="test-token")
    set_request_context(ctx)

    await send_progress(progress=75.0, total=100.0, message="Almost done")

    mock_session.send_progress_notification.assert_called_once_with(
        progress_token="test-token", progress=75.0, total=100.0, message="Almost done"
    )


@pytest.mark.asyncio
async def test_send_progress_function_without_context():
    """Test global send_progress function without context (should warn)."""
    # Should not raise, just log warning
    await send_progress(progress=50.0, total=100.0)


@pytest.mark.asyncio
async def test_request_context_manager(mock_session):
    """Test RequestContext as async context manager."""
    assert get_request_context() is None

    async with RequestContext(
        session=mock_session, progress_token="test-token", meta={"test": "data"}
    ) as ctx:
        # Inside context, should have access to context
        assert get_request_context() is not None
        assert get_request_context() is ctx
        assert ctx.session is mock_session
        assert ctx.progress_token == "test-token"
        assert ctx.meta == {"test": "data"}

        # Test sending progress inside context
        await send_progress(progress=30.0, total=100.0)

    # Outside context, should be cleared
    assert get_request_context() is None

    mock_session.send_progress_notification.assert_called_once()


@pytest.mark.asyncio
async def test_request_context_manager_nested():
    """Test nested RequestContext managers restore previous context."""
    session1 = AsyncMock()
    session2 = AsyncMock()

    async with RequestContext(session=session1, progress_token="token1") as ctx1:
        assert get_request_context() is ctx1

        async with RequestContext(session=session2, progress_token="token2") as ctx2:
            assert get_request_context() is ctx2
            assert ctx2.progress_token == "token2"

        # Should restore ctx1
        assert get_request_context() is ctx1
        assert ctx1.progress_token == "token1"

    # Should be cleared
    assert get_request_context() is None


@pytest.mark.asyncio
async def test_request_context_manager_with_exception(mock_session):
    """Test RequestContext cleans up even when exception occurs."""
    try:
        async with RequestContext(session=mock_session, progress_token="test"):
            assert get_request_context() is not None
            raise ValueError("Test error")
    except ValueError:
        pass

    # Context should still be cleared
    assert get_request_context() is None


@pytest.mark.asyncio
async def test_progress_with_integer_token(mock_session):
    """Test progress with integer token (some clients use integers)."""
    ctx = MCPRequestContext(session=mock_session, progress_token=12345)

    await ctx.send_progress(progress=10.0, total=100.0)

    mock_session.send_progress_notification.assert_called_once_with(
        progress_token=12345, progress=10.0, total=100.0, message=None
    )


@pytest.mark.asyncio
async def test_progress_step_counting(mock_session):
    """Test progress reporting with step counting."""
    ctx = MCPRequestContext(session=mock_session, progress_token="test-token")

    total_steps = 5
    for step in range(1, total_steps + 1):
        await ctx.send_progress(progress=step, total=total_steps, message=f"Step {step}")

    assert mock_session.send_progress_notification.call_count == total_steps

    # Check last call
    last_call = mock_session.send_progress_notification.call_args
    assert last_call.kwargs["progress"] == 5
    assert last_call.kwargs["total"] == 5
    assert last_call.kwargs["message"] == "Step 5"
