"""
Test API with real repository cloning.

Tests the full pipeline with spring-petclinic as a real Java repository.
"""

import json

import requests


def test_refactor_with_real_repo():
    """Test the refactor endpoint with a real Java repository."""
    BASE_URL = "http://localhost:8000"

    # Check server is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server not running. Start with: scripts/start_server.sh")
            return
    except requests.RequestException:
        print("❌ Server not running. Start with: scripts/start_server.sh")
        return

    print("=" * 80)
    print("TEST: Refactor with Real Repository Clone")
    print("=" * 80)

    # Start refactoring job with spring-petclinic
    refactor_request = {
        "user_id": "test_user",
        "user_prompt": "Add logging to the main application class",
        "github_credentials": {
            "repository_url": "https://github.com/spring-projects/spring-petclinic",
            "access_token": "mock_token_for_testing",  # Public repo
            "branch": "main",
        },
        "mode": "autonomous",
        "auto_fix_enabled": True,
        "max_retries": 2,
        "timeout_seconds": 300,
    }

    print("\n1️⃣  Starting refactor job...")
    print(f"   Repository: {refactor_request['github_credentials']['repository_url']}")
    print(f"   Prompt: {refactor_request['user_prompt']}")

    response = requests.post(f"{BASE_URL}/api/refactor", json=refactor_request, timeout=10)

    if response.status_code != 200:
        print(f"❌ Failed to start job: {response.status_code} {response.text}")
        return

    data = response.json()
    session_id = data["session_id"]
    print(f"✅ Job started: {session_id}")

    # Monitor progress via SSE
    print("\n2️⃣  Monitoring progress (SSE)...\n")

    try:
        with requests.get(
            f"{BASE_URL}/api/refactor/{session_id}/sse",
            stream=True,
            timeout=360,  # 6 minute timeout
        ) as sse_response:
            for line in sse_response.iter_lines():
                if not line:
                    continue

                line = line.decode("utf-8")

                if line.startswith("data:"):
                    data_str = line[5:].strip()

                    if data_str == "[DONE]":
                        print("\n✅ SSE Stream completed")
                        break

                    try:
                        event_data = json.loads(data_str)
                        stage = event_data.get("stage", "unknown")
                        status = event_data.get("status", "unknown")
                        progress = event_data.get("progress", 0.0)
                        message = event_data.get("message", "")

                        # Progress bar
                        bar_length = 30
                        filled = int(progress * bar_length)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        percentage = progress * 100

                        print(f"[{bar}] {percentage:5.1f}% | {stage:15s} | {message}")

                        # Check for clone success message
                        if "Repository cloned" in message:
                            print("   📦 Repository successfully cloned!")

                        # Check if completed or failed
                        if status in ["completed", "failed"]:
                            print(f"\n{'✅' if status == 'completed' else '❌'} Pipeline {status}")
                            break

                    except json.JSONDecodeError:
                        pass

    except requests.Timeout:
        print("\n⏱️  SSE stream timeout (may still be processing)")
    except KeyboardInterrupt:
        print("\n⏸️  Monitoring interrupted by user")

    # Get final status
    print("\n3️⃣  Fetching final status...")
    response = requests.get(f"{BASE_URL}/api/refactor/{session_id}", timeout=5)

    if response.status_code == 200:
        status_data = response.json()
        print(f"   Stage: {status_data['stage']}")
        print(f"   Status: {status_data['status']}")
        print(f"   Progress: {status_data['progress']:.0%}")
        print(f"   Message: {status_data['message']}")

        if status_data.get("data"):
            data = status_data["data"]
            print("\n   📊 Results:")
            if "files_changed" in data:
                print(f"      Files changed: {data['files_changed']}")
            if "validation_passed" in data:
                print(
                    f"      Validation: {'✅ Passed' if data['validation_passed'] else '❌ Failed'}"
                )

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_refactor_with_real_repo()
