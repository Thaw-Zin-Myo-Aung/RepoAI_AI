#!/bin/bash
# Start the RepoAI FastAPI server

echo "🚀 Starting RepoAI FastAPI server..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd /home/timmy/RepoAI_AI
uv run python -m repoai.api.main
