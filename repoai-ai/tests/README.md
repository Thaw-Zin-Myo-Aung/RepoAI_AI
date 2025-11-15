# Tests

Comprehensive test suite for RepoAI.

## Directory Structure

```
tests/
├── test_smoke.py           # Quick smoke tests
├── api/                    # API endpoint tests
│   ├── test_endpoints.py   # All REST endpoints
│   └── test_sse_streaming.py  # SSE progress streaming
└── integration/            # End-to-end tests (coming soon)
    └── (future tests)
```

## Running Tests

### Quick Smoke Test
```bash
uv run pytest tests/test_smoke.py -v
```

### API Endpoint Tests
```bash
# Start server first
./scripts/start_server.sh

# In another terminal, run API tests
uv run python tests/api/test_endpoints.py
```

### SSE Streaming Test
```bash
# Server must be running
uv run python tests/api/test_sse_streaming.py
```

### All Tests with pytest
```bash
uv run pytest tests/ -v
```

## Test Coverage

### ✅ API Tests (`tests/api/`)

**test_endpoints.py** - Comprehensive API testing:
- Health check endpoint (`/api/health`)
- Root endpoint (`/`)
- Readiness probe (`/api/health/ready`)
- Liveness probe (`/api/health/live`)
- Start refactor job (`POST /api/refactor`)
- Job status polling (`GET /api/refactor/{id}`)
- SSE streaming connection

**test_sse_streaming.py** - Real-time progress:
- SSE connection establishment
- Progress event streaming
- Stage transition tracking
- Progress bar visualization

### 🚧 Integration Tests (`tests/integration/`)

Coming soon:
- End-to-end pipeline execution
- GitHub repository cloning
- Java backend communication
- WebSocket bidirectional chat

## Test Requirements

The tests require these dependencies (already in `pyproject.toml`):
- `pytest` - Test framework
- `requests` - HTTP client
- FastAPI server running on `localhost:8000`

## Writing New Tests

### API Test Template
```python
import requests

BASE_URL = "http://localhost:8000"

def test_my_endpoint():
    response = requests.get(f"{BASE_URL}/api/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### Integration Test Template
```python
import pytest
from repoai.orchestrator import OrchestratorAgent

@pytest.mark.asyncio
async def test_pipeline_execution():
    # Setup
    orchestrator = OrchestratorAgent(...)
    
    # Execute
    result = await orchestrator.run("Test prompt")
    
    # Assert
    assert result.is_complete
```

## Continuous Integration

Tests are run automatically on:
- Git pre-commit (via pre-commit hooks)
- Push to main branch
- Pull requests

## Test Results

See [docs/testing.md](../docs/testing.md) for latest test results and findings.
