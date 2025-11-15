#!/bin/bash
# Test conversational intent detection through API endpoints

BASE_URL="http://localhost:8000/api/v1"

echo "========================================"
echo "Testing Conversational Intent Detection"
echo "========================================"
echo ""

# Test 1: Greeting
echo "Test 1: Greeting - 'hello'"
echo "----------------------------"
curl -s -X POST "$BASE_URL/refactor" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "user_prompt": "hello",
    "repository_url": "https://github.com/test/repo",
    "mode": "interactive-detailed",
    "github_credentials": {
      "token": "test_token",
      "username": "test_user"
    }
  }' | jq '.'

echo ""
echo ""

# Test 2: Capability question
echo "Test 2: Capability Question - 'what can you do?'"
echo "-------------------------------------------------"
curl -s -X POST "$BASE_URL/refactor" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "user_prompt": "what can you do?",
    "repository_url": "https://github.com/test/repo",
    "mode": "interactive-detailed",
    "github_credentials": {
      "token": "test_token",
      "username": "test_user"
    }
  }' | jq '.'

echo ""
echo ""

# Test 3: Refactoring request (should NOT be conversational)
echo "Test 3: Refactoring Request - 'Add JWT authentication'"
echo "-------------------------------------------------------"
curl -s -X POST "$BASE_URL/refactor" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "user_prompt": "Add JWT authentication",
    "repository_url": "https://github.com/test/repo",
    "mode": "interactive-detailed",
    "github_credentials": {
      "token": "test_token",
      "username": "test_user"
    }
  }' | jq '.'

echo ""
echo ""

# Test 4: SSE Stream for greeting
echo "Test 4: SSE Stream for 'hi' (first 10 events)"
echo "----------------------------------------------"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/refactor" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "user_prompt": "hi",
    "repository_url": "https://github.com/test/repo",
    "mode": "interactive-detailed",
    "github_credentials": {
      "token": "test_token",
      "username": "test_user"
    }
  }')

SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')
echo "Session ID: $SESSION_ID"
echo ""

if [ "$SESSION_ID" != "null" ]; then
  echo "SSE Events:"
  curl -s -N "$BASE_URL/refactor/$SESSION_ID/sse" | head -20
fi

echo ""
echo "========================================"
echo "Testing Complete"
echo "========================================"
