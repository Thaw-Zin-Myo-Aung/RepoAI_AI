# RepoAI Workspace Structure (Cleaned)

## 📁 Project Layout

```
RepoAI_AI/
├── 📄 Core Files
│   ├── README.md                    # Project overview
│   ├── pyproject.toml               # Python dependencies
│   ├── LICENSE                      # MIT License
│   └── .env                         # API keys & config
│
├── 🔧 src/repoai/                   # Main Source Code
│   ├── agents/                      # AI Agents
│   │   ├── intake_agent.py         # Parse user requests
│   │   ├── planner_agent.py        # Create refactor plans
│   │   ├── transformer_agent.py    # Generate code changes
│   │   ├── validator_agent.py      # Validate changes
│   │   ├── pr_narrator_agent.py    # Create PR descriptions
│   │   └── prompts/                # Agent prompts
│   │
│   ├── api/                        # FastAPI Server
│   │   ├── main.py                 # App entry point
│   │   ├── models.py               # Request/Response models
│   │   └── routes/
│   │       ├── health.py           # Health checks
│   │       ├── refactor.py         # SSE streaming endpoints (with validation confirmation)
│   │       └── websocket.py        # WebSocket for chat
│   │
│   ├── orchestrator/               # Pipeline Coordination
│   │   ├── orchestrator_agent.py   # Base orchestrator (with validation confirmation)
│   │   ├── chat_orchestrator.py    # Interactive mode
│   │   ├── models.py               # Pipeline state models (AWAITING_VALIDATION_CONFIRMATION)
│   │   └── prompts.py              # Orchestrator prompts
│   │
│   ├── llm/                        # LLM Infrastructure
│   │   ├── pydantic_ai_adapter.py  # PydanticAI wrapper
│   │   ├── router.py               # Model routing
│   │   ├── model_roles.py          # Agent roles
│   │   └── model_registry.py       # Model configs
│   │
│   ├── models/                     # Data Models
│   │   ├── job_spec.py            # User request spec
│   │   ├── refactor_plan.py       # Refactor plan
│   │   ├── code_change.py         # Code changes
│   │   └── validation_result.py   # Validation results
│   │
│   ├── dependencies/               # Dependency Injection
│   │   └── base.py                # Agent dependencies
│   │
│   ├── parsers/                    # Code Parsers
│   │   └── java_parser.py         # Java AST parser
│   │
│   ├── tools/                      # Agent Tools
│   │   ├── code_search.py         # Code search tool
│   │   └── maven_utils.py         # Maven operations
│   │
│   ├── utils/                      # Utilities
│   │   ├── file_operations.py     # File I/O
│   │   ├── git_utils.py           # Git operations
│   │   ├── java_build_utils.py    # Maven/Gradle builds
│   │   └── logger.py              # Logging config
│   │
│   ├── rag/                        # RAG (Future)
│   │   └── retriever.py           # Code retrieval
│   │
│   ├── services/                   # Business Logic
│   │   └── refactor_service.py    # Refactoring service
│   │
│   ├── config/                     # Configuration
│   │   └── settings.py            # App settings
│   │
│   └── explainability/             # Transparency
│       ├── confidence.py          # Confidence scoring
│       └── metadata.py            # Change metadata
│
├── 🧪 tests/                       # Tests
│   ├── api/
│   │   ├── test_endpoints.py      # API integration tests
│   │   ├── test_sse_streaming.py  # SSE streaming tests
│   │   ├── test_with_real_repo.py # Real repo tests
│   │   └── test_message_buffering.py # Message buffer tests
│   │
│   ├── integration/
│   │   ├── test_full_pipeline.py  # End-to-end tests
│   │   └── test_orchestrator_workflow.py # Orchestrator tests
│   │
│   ├── test_smoke.py              # Basic smoke tests
│   ├── test_git_utils.py          # Git utility tests
│   ├── test_file_operations.py    # File operation tests
│   ├── test_java_build_utils.py   # Build utility tests
│   ├── test_planner_agent.py      # Planner agent tests
│   ├── test_circular_import_fix.py # Import fix tests
│   └── test_build_output_streaming.py # Build streaming tests
│
├── 📚 docs/                        # Documentation
│   ├── README.md                  # Architecture overview
│   ├── testing.md                 # Testing guide
│   ├── streaming_implementation.md # SSE streaming docs
│   ├── streaming_vs_batch.md      # Implementation comparison
│   ├── transformer_improvements.md # Code generation docs
│   ├── phase3_repository_cloning.md # Git integration
│   ├── phase_4c_real_compilation.md # Build integration
│   ├── phase_5.md                 # Phase 5 implementation
│   ├── BUILD_SYSTEM_POLICY.md     # Build system rules
│   ├── POSTMAN_TESTING_GUIDE.md   # API testing guide
│   ├── BACKEND_INTEGRATION_SSE.md # Backend SSE integration
│   ├── build_streaming_implementation_summary.md # Build streaming
│   ├── conversational_api_configuration.md # Chat API config
│   ├── conversational_intent_detection.md # Intent detection
│   ├── demo_configuration.md      # Demo setup
│   ├── file_content_streaming.md  # File streaming
│   ├── frontend_diff_rendering.md # Diff rendering
│   ├── java_backend_integration.md # Java backend docs
│   ├── llm_confirmations_summary.md # LLM confirmation flow
│   ├── push_confirmation_llm.md   # Push confirmation
│   └── streaming_build_output.md  # Build output streaming
│
├── 💡 usage_examples/             # Example Scripts
│   ├── intake2planner.py         # Intake → Planner demo
│   ├── transformer_workflow.py   # Full pipeline demo
│   ├── validator_workflow.py     # Validation demo
│   ├── livetest_java_parser.py  # Parser testing
│   └── test_java_parser.py      # Parser unit tests
│
├── 📓 notebooks/                  # Jupyter Notebooks
│   ├── 00_quickstart.ipynb       # Quick start guide
│   ├── intake_agent.ipynb        # Intake agent exploration
│   └── test_pydantic_ai_adapter.ipynb # Adapter testing
│
└── 🔨 scripts/                    # Utility Scripts
    ├── start_server.sh           # Start FastAPI server
    ├── run_api_tests.sh          # Run API tests
    ├── test_conversational_api.sh # Test chat API
    └── validate_for_demo.sh      # Demo validation
```

## 🎯 Key Entry Points

### 1. **API Server**
```bash
uv run python -m repoai.api.main
# or
./scripts/start_server.sh
```

### 2. **Usage Examples**
```bash
uv run python usage_examples/transformer_workflow.py
```

### 3. **Tests**
```bash
# All tests
uv run pytest

# API tests only
uv run pytest tests/api/

# Integration tests
uv run pytest tests/integration/
```

## 📊 Code Statistics

- **Total Python Files**: 73
- **Main Source Lines**: ~15,000
- **Test Files**: 13
- **Documentation Files**: 22
- **Agents**: 5 specialized agents
- **API Endpoints**: 9 (health, refactor, SSE, confirm-plan, confirm-validation, confirm-push, WebSocket)
- **Confirmation Checkpoints**: 3 (plan, validation, push)

## 🧹 Recently Cleaned

### Removed Files (Nov 13, 2025)
- ❌ 8 old log files
- ❌ 5 obsolete documentation files
- ❌ 8 debug/manual test files
- ❌ 5 usage example log files
- ❌ 1 empty placeholder file

### Kept Files
- ✅ All core source code
- ✅ Essential tests (12 files)
- ✅ Key documentation (8 files)
- ✅ Usage examples (5 files)

## 🏗️ Architecture Highlights

### Multi-Agent Pipeline
```
User Prompt
    ↓
[Intake Agent] → Parse request
    ↓
[Planner Agent] → Create plan
    ↓
[Transformer Agent] → Generate code (with tool calling!)
    ↓
[Validator Agent] → Validate changes
    ↓
[PR Narrator Agent] → Create PR description
```

### SSE Streaming
- Real-time progress updates
- Message buffering for late connections
- Multiple event types (step_started, file_modified, etc.)
- Tool calling during streaming (NEW!)

### LLM Infrastructure
- Role-based model routing (INTAKE, PLANNER, CODER, PR, VALIDATOR)
- PydanticAI adapter with tool support
- Streaming and batch modes
- Confidence scoring and metadata

## 🚀 Current Focus (Updated Nov 14, 2025)

1. **Validation Confirmation Checkpoint** - Just implemented! ✅
   - 3 modes: full (compile + tests), compile_only (compile only), skip
   - LLM-powered natural language interpretation
   - Interactive-detailed mode support
2. **Error Handling Improvements** - Just completed! ✅
   - Clean token limit error logging
   - Fixed duplicate file streaming in transformer
3. **Backend Integration** - SSE streaming to Java Spring Boot
4. **Demo Preparation** - Nov 17, 2025 deadline
5. **Performance Optimization** - Token limit awareness

## 📖 Documentation Priority

1. **Must Read**:
   - `README.md` - Start here
   - `docs/README.md` - Architecture overview
   - `docs/streaming_implementation.md` - SSE implementation

2. **For Development**:
   - `docs/testing.md` - Testing guide
   - `docs/BUILD_SYSTEM_POLICY.md` - Build rules

3. **For Understanding**:
   - `docs/transformer_improvements.md` - Code generation
   - `usage_examples/transformer_workflow.py` - Full example

## 🎓 Code Readability

### Well-Structured Files
- ✅ Clear module organization
- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ No unused imports (verified by ruff)
- ✅ Consistent formatting (black)

### Complexity
- Some agent creation functions are complex (C901) but justified
- Tools require multiple conditional branches
- Core business logic is straightforward

## 📝 Next Steps

1. Test tool calling during streaming
2. Verify no "File already exists" errors
3. Complete backend integration
4. Performance validation
5. Demo preparation
