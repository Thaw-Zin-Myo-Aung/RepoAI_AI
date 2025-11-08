#!/usr/bin/env python
"""
Test script for RepoAI FastAPI endpoints.

Run the API server first:
    uv run python -m repoai.api.main

Then run this script in another terminal:
    uv run python test_api.py
"""

import json
import sys
import time

import requests

BASE_URL = "http://localhost:8000"


def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_health() -> bool:
    """Test health endpoint."""
    print_section("TEST 1: Health Check Endpoint")

    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Health check PASSED")
            return True
        else:
            print("❌ Health check FAILED")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        print("\n⚠️  Make sure the server is running:")
        print("    uv run python -m repoai.api.main")
        return False


def test_root() -> bool:
    """Test root endpoint."""
    print_section("TEST 2: Root Endpoint")

    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Root endpoint PASSED")
            return True
        else:
            print("❌ Root endpoint FAILED")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False


def test_readiness() -> bool:
    """Test readiness endpoint."""
    print_section("TEST 3: Readiness Check")

    try:
        response = requests.get(f"{BASE_URL}/api/health/ready", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Readiness check PASSED")
            return True
        else:
            print("❌ Readiness check FAILED")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False


def test_liveness() -> bool:
    """Test liveness endpoint."""
    print_section("TEST 4: Liveness Check")

    try:
        response = requests.get(f"{BASE_URL}/api/health/live", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Liveness check PASSED")
            return True
        else:
            print("❌ Liveness check FAILED")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False


def test_refactor_endpoint() -> str | None:
    """Test refactor endpoint (start job)."""
    print_section("TEST 5: Start Refactor Job")

    request_data = {
        "user_id": "test_user",
        "user_prompt": "Add error handling and logging to all service methods",
        "github_credentials": {
            "access_token": "mock_token_for_testing",
            "repository_url": "https://github.com/test/mock-java-repo",
            "branch": "main",
        },
        "mode": "autonomous",
        "auto_fix_enabled": True,
        "max_retries": 2,
        "timeout_seconds": 120,
    }

    print("Request Body:")
    print(json.dumps(request_data, indent=2))
    print()

    try:
        response = requests.post(f"{BASE_URL}/api/refactor", json=request_data, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            session_id = response.json().get("session_id")
            print(f"\n✅ Refactor job started with session_id: {session_id}")
            return session_id
        else:
            print("❌ Failed to start refactor job")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return None


def test_status_endpoint(session_id: str) -> bool:
    """Test status endpoint."""
    print_section(f"TEST 6: Check Job Status (session: {session_id})")

    try:
        response = requests.get(f"{BASE_URL}/api/refactor/{session_id}", timeout=5)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response:\n{json.dumps(data, indent=2)}")
            print(
                f"\n✅ Status retrieved - Stage: {data.get('stage')}, Progress: {data.get('progress')}"
            )
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ Failed to get status")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False


def test_sse_stream(session_id: str, duration: int = 10) -> bool:
    """Test SSE streaming endpoint."""
    print_section(f"TEST 7: SSE Progress Stream (session: {session_id})")
    print(f"Streaming for {duration} seconds...\n")

    try:
        with requests.get(
            f"{BASE_URL}/api/refactor/{session_id}/sse", stream=True, timeout=duration + 5
        ) as response:

            if response.status_code != 200:
                print(f"❌ SSE stream failed with status: {response.status_code}")
                return False

            event_count = 0
            start_time = time.time()

            for line in response.iter_lines():
                if time.time() - start_time > duration:
                    print(f"\n⏱️  Stopped streaming after {duration}s")
                    break

                if line:
                    decoded = line.decode("utf-8")

                    if decoded.startswith("data:"):
                        event_count += 1
                        data = decoded[5:].strip()

                        try:
                            event_data = json.loads(data)
                            print(
                                f"Event {event_count}: stage={event_data.get('stage')}, "
                                f"progress={event_data.get('progress'):.2f}, "
                                f"message={event_data.get('message')}"
                            )
                        except json.JSONDecodeError:
                            print(f"Event {event_count}: {data}")

            if event_count > 0:
                print(f"\n✅ SSE streaming PASSED - Received {event_count} events")
                return True
            else:
                print("\n⚠️  No events received")
                return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return False


def main() -> None:
    """Run all tests."""
    print("\n" + "🚀" * 40)
    print("  RepoAI API Test Suite")
    print("🚀" * 40)

    results = {}

    # Test basic endpoints
    results["health"] = test_health()
    if not results["health"]:
        print("\n❌ Cannot continue - server is not responding")
        sys.exit(1)

    results["root"] = test_root()
    results["readiness"] = test_readiness()
    results["liveness"] = test_liveness()

    # Test refactor workflow
    session_id = test_refactor_endpoint()

    if session_id:
        results["refactor_start"] = True

        # Wait a moment for job to start
        print("\n⏳ Waiting 2 seconds for job to initialize...")
        time.sleep(2)

        results["status"] = test_status_endpoint(session_id)
        results["sse"] = test_sse_stream(session_id, duration=10)
    else:
        results["refactor_start"] = False
        results["status"] = False
        results["sse"] = False

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20s}: {status}")

    print(f"\n{'=' * 80}")
    print(f"Total: {passed}/{total} tests passed")
    print(f"{'=' * 80}\n")

    if passed == total:
        print("🎉 All tests PASSED!")
        sys.exit(0)
    else:
        print("⚠️  Some tests FAILED - check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
