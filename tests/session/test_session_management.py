# tests/session/test_session_management.py - Final Fixed Version
"""
Fixed session management tests with proper concurrent session isolation.
"""

import asyncio

import pytest

from tests.conftest import (
    MockMCPSessionManager,
    MockSessionContext,
    mock_session_ctx,
)


class TestSessionContext:
    """Test the SessionContext context manager."""

    @pytest.mark.asyncio
    async def test_session_context_exception_handling(self):
        """Test SessionContext handles exceptions properly."""
        session_manager = MockMCPSessionManager()

        # Create a session and set as previous context
        session_id = await session_manager.create_session()

        # CRITICAL: Set the previous context using the context variable, not string
        mock_session_ctx.set("previous_session")
        session_manager._current_session = "previous_session"

        try:
            async with MockSessionContext(session_manager, session_id=session_id):
                # Verify we're in the new session context
                current = mock_session_ctx.get()
                assert current == session_id
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should restore previous context
        current_after = mock_session_ctx.get()
        assert current_after == "previous_session"


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self):
        """Test concurrent session operations with proper isolation."""
        session_manager = MockMCPSessionManager()

        # Pre-create sessions for each worker to ensure they're different
        session1 = await session_manager.create_session(
            user_id="user1", metadata={"worker_id": "worker1"}
        )
        session2 = await session_manager.create_session(
            user_id="user2", metadata={"worker_id": "worker2"}
        )
        session3 = await session_manager.create_session(
            user_id="user3", metadata={"worker_id": "worker3"}
        )

        # Map workers to their pre-created sessions
        worker_sessions = {
            "worker1": session1,
            "worker2": session2,
            "worker3": session3,
        }

        results = {}

        async def session_worker(worker_id, user_id):
            # Use the pre-created session for this worker
            worker_session_id = worker_sessions[worker_id]

            # Work directly with the specific session (no context switching needed)
            # Update session metadata using the session_id directly
            await session_manager.update_session_metadata(
                worker_session_id, {"worker_id": worker_id, "processed": True}
            )

            # Get session info using the session_id directly
            info = await session_manager.get_session_info(worker_session_id)

            results[worker_id] = {
                "session_id": worker_session_id,
                "user_id": info["user_id"],
                "worker_id": info["custom_metadata"]["worker_id"],
            }

        # Run concurrent workers
        workers = [
            session_worker("worker1", "user1"),
            session_worker("worker2", "user2"),
            session_worker("worker3", "user3"),
        ]
        await asyncio.gather(*workers)

        # Verify each worker maintained its own session
        for i in range(1, 4):
            worker_key = f"worker{i}"
            user_key = f"user{i}"

            assert worker_key in results, f"Results missing for {worker_key}"
            assert (
                results[worker_key]["user_id"] == user_key
            ), f"User ID mismatch for {worker_key}: expected {user_key}, got {results[worker_key]['user_id']}"
            assert (
                results[worker_key]["worker_id"] == worker_key
            ), f"Worker ID mismatch for {worker_key}"

        # Verify sessions are different
        session_ids = [results[f"worker{i}"]["session_id"] for i in range(1, 4)]
        assert len(set(session_ids)) == 3, f"Sessions should be different but got: {session_ids}"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
