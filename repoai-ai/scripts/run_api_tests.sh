#!/bin/bash
# Quick test runner for RepoAI API

set -e

echo "🧪 RepoAI API Test Runner"
echo "========================="
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "❌ Server is not running!"
    echo ""
    echo "Start the server first:"
    echo "  ./scripts/start_server.sh"
    echo ""
    exit 1
fi

echo "✅ Server is running"
echo ""

# Run comprehensive endpoint tests
echo "📋 Running endpoint tests..."
uv run python tests/api/test_endpoints.py

echo ""
echo "========================="
echo "✅ All tests completed!"
