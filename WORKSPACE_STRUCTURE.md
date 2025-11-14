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
│   │   ├── intake_agent.py         # Parse user requests → JobSpec
│   │   ├── planner_agent.py        # Create RefactorPlan with risk analysis
│   │   ├── transformer_agent.py    # Generate code changes (batch or streaming)
│   │   ├── validator_agent.py      # Compile, test and run static analysis
│   │   ├── pr_narrator_agent.py    # Create PR descriptions
│   │   └── prompts/                # System and tool prompts
│   │
│   ├── api/                        # FastAPI Server
│   │   ├── main.py                 # App entry point (includes SSE & WebSocket)
│   │   ├── models.py               # API request/response models
│   │   ├── routes/
│   │   │   ├── health.py           # Health checks
│   │   │   ├── refactor.py         # Refactor endpoints & SSE streaming
│   │   │   ├── websocket.py        # WebSocket for chat/interactive mode
│   │   │   └── embeddings.py       # (Planned) RAG embedding endpoint
│   │   └── deps.py                 # FastAPI dependency overrides
│   │
│   ├── orchestrator/               # Pipeline Coordination
│   │   ├── orchestrator_agent.py   # Autonomous orchestrator with validation/push confirmations
│   │   ├── chat_orchestrator.py    # Interactive orchestrator supporting chat confirmations
│   │   ├── models.py               # Pipeline state models & enums
│   │   └── prompts.py              # Orchestrator prompts & templates
│   │
│   ├── llm/                        # LLM Infrastructure
│   │   ├── pydantic_ai_adapter.py  # Adapter to call Gemini models with tool support
│   │   ├── router.py               # Model routing & fallback logic
│   │   ├── model_roles.py          # Role enumeration for agents
│   │   └── model_registry.py       # Model configs & environment loading
│   │
│   ├── models/                     # Data Models (Pydantic)
│   │   ├── job_spec.py            # Structured job specification
│   │   ├── refactor_plan.py       # Plan with steps, durations and risk
│   │   ├── code_change.py         # Code change representation
│   │   └── validation_result.py   # Validation result & metadata
│   │
│   ├── dependencies/               # Dependency Injection
│   │   └── base.py                # Agents’ dependency container
│   │
│   ├── parsers/                    # Code Parsers
│   │   └── java_ast_parser.py     # Java AST parser for context extraction
│   │
│   ├── tools/                      # Agent Tools
│   │   ├── code_search.py         # Code search & retrieval utilities
│   │   └── maven_utils.py         # Maven operations (pom parsing, dependency add)
│   │
│   ├── utils/                      # Utilities
│   │   ├── file_operations.py     # Reading and writing files
│   │   ├── git_utils.py           # Git clone, commit and branch utilities
│   │   ├── java_build_utils.py    # Maven/Gradle compilation & test execution
│   │   └── logger.py              # Logging configuration
│   │
│   ├── rag/                        # Retrieval‑Augmented Generation (Future)
│   │   └── retriever.py           # Placeholder for vector search integration
│   │
│   ├── services/                   # Business Logic
│   │   └── refactor_service.py    # Orchestrator wrapper & business rules
│   │
│   ├── config/                     # Configuration
│   │   └── settings.py            # App settings & environment variables
│   │
│   └── explainability/             # Transparency & Metadata
│       ├── confidence.py          # Confidence scoring for LLM outputs
│       └── metadata.py            # Change metadata & provenance
│
├── 🧪 tests/                       # Tests
│   ├── api/                        # API integration & streaming tests
│   ├── integration/                # Full pipeline & orchestrator tests
│   ├── test_smoke.py              # Basic smoke tests
│   ├── test_git_utils.py          # Git utility tests
│   ├── test_file_operations.py    # File I/O tests
│   ├── test_java_build_utils.py   # Build utility tests
│   ├── test_planner_agent.py      # Planner agent tests
│   ├── test_circular_import_fix.py # Import fix tests
│   └── test_build_output_streaming.py # Build streaming tests
│
├── 📚 docs/                        # Documentation
│   ├── README.md                  # Architecture overview & features
│   ├── testing.md                 # Phase 1 testing results
│   ├── BUILD_SYSTEM_POLICY.md     # Build system rules
│   ├── POSTMAN_TESTING_GUIDE.md   # API testing guide
│   ├── push_confirmation_llm.md   # Push confirmation design
│   ├── java_backend_integration.md # Java backend integration guide
│   ├── conversational_api_configuration.md # Chat API configuration
│   ├── transformer_improvements.md # Additional transformer notes
│   └── ...                        # Other docs (see docs/)
│
├── 💡 usage_examples/             # Example Scripts
│   ├── intake2planner.py         # Intake → Planner demo
│   ├── transformer_workflow.py   # Full pipeline demo
│   ├── validator_workflow.py     # Validation demo
│   ├── livetest_java_parser.py  # Parser testing
│   └── test_java_parser.py      # Parser unit tests
│
├── 📓 notebooks/                  # Jupyter Notebooks
│   ├── 00_quickstart.ipynb       # Quick start exploration
│   ├── intake_agent.ipynb        # Intake agent exploration
│   └── test_pydantic_ai_adapter.ipynb # Adapter testing
│
└── 🔨 scripts/                    # Utility Scripts
    ├── start_server.sh           # Start FastAPI server
    ├── run_api_tests.sh          # Run API tests
    ├── test_conversational_api.sh # Test chat API endpoints
    └── validate_for_demo.sh      # Demo validation & build

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
