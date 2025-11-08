# Documentation

RepoAI documentation and guides.

## Available Documentation

### Testing
- **[testing.md](testing.md)** - API testing results and findings

## Quick Links

- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when server running)
- [Tests README](../tests/README.md) - How to run tests
- [Scripts README](../scripts/README.md) - Available utility scripts

## Architecture Overview

```
RepoAI Architecture
===================

┌─────────────┐
│ Java Backend│
│  (Spring)   │
└──────┬──────┘
       │ HTTP/WebSocket
       ▼
┌─────────────────────┐
│  FastAPI API Layer  │
│  (Python)           │
│  - REST endpoints   │
│  - SSE streaming    │
│  - WebSocket        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Orchestrator       │
│  - OrchestratorAgent│
│  - ChatOrchestrator │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  5 Specialized      │
│  Agents             │
│  1. Intake          │
│  2. Planner         │
│  3. Transformer     │
│  4. Validator       │
│  5. PR Narrator     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  LLM Provider       │
│  (Google Gemini)    │
└─────────────────────┘
```

## Key Features

### Autonomous Mode
- POST request triggers pipeline
- Background execution
- SSE streaming for real-time progress
- Polling for status updates

### Interactive Mode
- WebSocket bidirectional communication
- User confirmations at key points
- Plan approval workflow
- Modification requests

### Progress Tracking
Real-time updates at each stage:
- 🚀 Pipeline start
- 📥 Stage 1: Intake (analyzing request)
- 📋 Stage 2: Planning (creating refactoring plan)
- 🔨 Stage 3: Transformation (generating code)
- 🔍 Stage 4: Validation (checking code quality)
- 📝 Stage 5: Narration (PR description)
- 🎉 Completion

## Development Workflow

1. **Start Server**
   ```bash
   ./scripts/start_server.sh
   ```

2. **Run Tests**
   ```bash
   ./scripts/run_api_tests.sh
   ```

3. **Check Results**
   - View logs in terminal
   - Access API docs: http://localhost:8000/docs

## Future Documentation

Planned documentation:
- API endpoint specifications
- Agent architecture details
- LLM prompt engineering guide
- Deployment guide
- Contribution guidelines
