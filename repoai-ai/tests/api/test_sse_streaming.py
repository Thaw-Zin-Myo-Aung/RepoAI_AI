#!/usr/bin/env python
"""
Quick test for SSE progress streaming with the updated orchestrator.
"""

import json
import time

import requests

BASE_URL = "http://localhost:8000"


def test_sse_with_progress():
    """Test SSE streaming with progress updates."""
    print("=" * 80)
    print("Testing SSE Progress Streaming")
    print("=" * 80)

    # Start a refactor job
    print("\n1. Starting refactor job...")
    request_data = {
        "user_id": "test_user",
        "user_prompt": "Add logging to all public methods",
        "github_credentials": {
            "access_token": "mock_token",
            "repository_url": "https://github.com/test/repo",
            "branch": "main",
        },
        "mode": "autonomous",
        "max_retries": 1,
        "timeout_seconds": 120,
    }

    response = requests.post(f"{BASE_URL}/api/refactor", json=request_data)

    if response.status_code != 200:
        print(f"❌ Failed to start job: {response.status_code}")
        return

    data = response.json()
    session_id = data["session_id"]
    print(f"✅ Job started: {session_id}")
    print(f"   SSE URL: {data['sse_url']}")

    # Connect to SSE stream
    print("\n2. Connecting to SSE stream...")
    print("-" * 80)

    try:
        with requests.get(
            f"{BASE_URL}{data['sse_url']}",
            stream=True,
            timeout=60,  # 60 second timeout
        ) as sse_response:
            if sse_response.status_code != 200:
                print(f"❌ SSE connection failed: {sse_response.status_code}")
                return

            print("✅ SSE connected! Streaming events...\n")

            event_count = 0
            start_time = time.time()
            last_stage = None

            for line in sse_response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")

                    if decoded.startswith("event:"):
                        # Event type line (not currently used)
                        pass

                    elif decoded.startswith("data:"):
                        event_count += 1
                        data_str = decoded[5:].strip()

                        try:
                            event_data = json.loads(data_str)
                            stage = event_data.get("stage", "unknown")
                            progress = event_data.get("progress", 0)
                            message = event_data.get("message", "")

                            # Show stage transitions
                            if stage != last_stage:
                                print(f"\n📍 Stage: {stage.upper()}")
                                last_stage = stage

                            # Show progress
                            bar_length = 40
                            filled = int(bar_length * progress)
                            bar = "█" * filled + "░" * (bar_length - filled)

                            print(f"   [{bar}] {progress*100:5.1f}% | {message[:60]}")

                        except json.JSONDecodeError:
                            print(f"   Raw: {data_str[:80]}")

                # Check for completion
                elapsed = time.time() - start_time
                if elapsed > 60:
                    print("\n⏱️  Timeout after 60s")
                    break

            print("\n" + "-" * 80)
            print("\n📊 Summary:")
            print(f"   Total events received: {event_count}")
            print(f"   Duration: {elapsed:.1f}s")

            if event_count > 0:
                print("\n✅ SSE STREAMING WORKS! Progress updates received.")
            else:
                print("\n⚠️  No events received (pipeline may be slow)")

    except requests.exceptions.Timeout:
        print("\n⏱️  Request timeout")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    test_sse_with_progress()
