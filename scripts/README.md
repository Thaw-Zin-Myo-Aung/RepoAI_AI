# Scripts

Utility scripts for development and testing.

## Available Scripts

### `start_server.sh`

Starts the RepoAI FastAPI server for local testing.

**Usage:**
```bash
./scripts/start_server.sh
```

**What it does:**
- Starts uvicorn server on http://localhost:8000
- Enables auto-reload for development
- Logs output to console

**Access:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

**Stop Server:**
Press `Ctrl+C` in the terminal

---

## Future Scripts

Could add:
- `test_server.sh` - Run all API tests
- `setup_dev.sh` - Development environment setup
- `deploy.sh` - Deployment script
- `clone_repo.sh` - GitHub repository cloning helper
