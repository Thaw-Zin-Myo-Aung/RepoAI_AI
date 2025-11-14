"""Test message buffering for late SSE connections."""

import json

import pytest
from fastapi.testclient import TestClient

from repoai.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_greeting_buffered_for_late_sse_connection(client):
    """
    Test that conversational greeting is buffered and available
    when SSE client connects late (after response completes).

    This simulates backend integration where SSE connection
    might be established after the greeting is already sent.
    """
    # 1. Start conversational request (greeting)
    response = client.post(
        "/api/refactor",
        json={
            "user_id": "test_user",
            "user_prompt": "hello",
            "github_credentials": {
                "access_token": "test_token",
                "repository_url": "https://github.com/test/repo",
                "branch": "main",
            },
            "mode": "autonomous",
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]

    # 2. Simulate delay before SSE connection (conversational response completes in <300ms)
    # Wait longer than conversation time to ensure response is already buffered
    import time

    time.sleep(1.0)

    # 3. Connect to SSE endpoint (late connection)
    with client.stream("GET", f"/api/refactor/{session_id}/sse") as sse_stream:
        events = []

        # Read all events from stream
        for line in sse_stream.iter_lines():
            if line.startswith("data: "):
                event_data = line[6:]  # Remove "data: " prefix
                try:
                    events.append(json.loads(event_data))
                except json.JSONDecodeError:
                    pass

        # Verify we got buffered greeting message
        assert len(events) >= 1, "Should receive buffered greeting message"

        # Check that greeting was delivered
        greeting_found = False
        for event in events:
            if "Hello" in event.get("message", "") or "RepoAI" in event.get("message", ""):
                greeting_found = True
                break

        assert greeting_found, f"Greeting not found in buffered events: {events}"

        # For conversational responses, we should only get the greeting message (no completion message)
        # The greeting message itself indicates the conversation is complete


def test_pipeline_events_buffered_for_late_connection(client):
    """
    Test that pipeline events are buffered when SSE connects late.

    This is less critical than greetings (pipeline takes longer),
    but verifies buffer works for all event types.
    """
    # Start pipeline (will fail fast without real repo, but events still buffered)
    response = client.post(
        "/api/refactor",
        json={
            "user_id": "test_user",
            "user_prompt": "add logging",
            "github_credentials": {
                "access_token": "fake_token",
                "repository_url": "https://github.com/fake/repo",
                "branch": "main",
            },
            "mode": "autonomous",
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]

    # Wait for pipeline to complete (will fail on clone, but events buffered)
    import time

    time.sleep(2.0)

    # Connect to SSE (late)
    with client.stream("GET", f"/api/refactor/{session_id}/sse") as sse_stream:
        events = []

        for line in sse_stream.iter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                try:
                    events.append(json.loads(event_data))
                except json.JSONDecodeError:
                    pass

        # Should have received buffered events (even if pipeline failed)
        assert len(events) >= 1, "Should receive buffered events"

        # Verify we got status update (either failed or some progress)
        assert any("stage" in event for event in events), "Should have stage updates"


def test_immediate_sse_connection_no_buffer_needed(client):
    """
    Test that immediate SSE connection works (no buffering needed).

    This is the normal case where SSE connects before events are sent.
    """
    # Start conversational request
    response = client.post(
        "/api/refactor",
        json={
            "user_id": "test_user",
            "user_prompt": "hi there",
            "github_credentials": {
                "access_token": "test_token",
                "repository_url": "https://github.com/test/repo",
                "branch": "main",
            },
            "mode": "autonomous",
        },
    )

    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]

    # Connect to SSE immediately (no delay)
    with client.stream("GET", f"/api/refactor/{session_id}/sse") as sse_stream:
        events = []

        for line in sse_stream.iter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                try:
                    events.append(json.loads(event_data))
                except json.JSONDecodeError:
                    pass

        # Should receive greeting via queue (not buffer)
        assert len(events) >= 1
        greeting_found = any(
            "Hello" in event.get("message", "") or "RepoAI" in event.get("message", "")
            for event in events
        )
        assert greeting_found, "Should receive greeting"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
