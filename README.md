# RepoAI – AI Service Overview

RepoAI is the intelligent core of the refactoring assistant.  It receives user prompts and repository access data from the backend, orchestrates specialized AI agents and returns validated, refactored code with supporting evidence.

> **📁 Workspace Structure:** See [WORKSPACE_STRUCTURE.md](./WORKSPACE_STRUCTURE.md) for the full directory layout and code organization.

## How It Works

### 1️⃣ Request Intake
The backend (Spring Boot) sends a POST request to the AI service containing:
- **User prompt** – the requested refactor or analysis  
- **GitHub credentials** – repository access token and metadata  
- **Optional scope** – specific file paths, branch, or constraints  

A session is initialized and an orchestrated agent workflow begins.

### 2️⃣ Agentic Workflow
RepoAI uses modular agents that can be tested or replaced independently.  The core pipeline is:

| Agent                | Role                     | Highlights |
|----------------------|--------------------------|-----------|
| **Intake Agent**     | Prompt parsing           | Interprets the user prompt and produces a structured `JobSpec` describing the intended changes. |
| **Planner Agent**    | Plan generation          | Generates a detailed `RefactorPlan`, assigning risk levels to each step and estimating durations based on repository context.  Plans include mitigation strategies for high‑risk steps. |
| **Transformer Agent**| Code refactoring         | Applies code changes using deterministic codemods and large‑language models.  Supports both batch mode and streaming mode, yielding file‑by‑file updates for real‑time feedback. |
| **Validator Agent**  | Quality assurance        | Compiles the project, runs unit tests and performs static analysis (code quality, Spring conventions, security, test coverage).  It returns a `ValidationResult` with pass/fail, confidence and coverage metrics. |
| **PR Narrator Agent**| Documentation            | Summarizes the changes and validation outcomes into a human‑readable pull‑request description for reviewers. |
| **Policy Gate**      | Safety check             | Verifies branch protection, change size and non‑destructive operations before pushing changes. |

### 🧮 Orchestration and Error Recovery
A central `OrchestratorAgent` coordinates the pipeline.  It manages session state, risk‑aware decision making and retries.  If validation fails, it consults an LLM with retry strategy instructions to decide whether to retry, modify the plan or abort.  A backup of modified files is created before transformation, enabling rollback on critical errors.

### 💬 Interactive Mode
Use `ChatOrchestrator` for human‑in‑the‑loop refactoring.  It extends the base orchestrator to request user confirmations at key points, such as plan approval, applying changes and handling validation failures.  Users can modify the plan or abort via chat messages.

### 📶 Streaming & Progress Updates
Enable streaming mode to receive real‑time updates as each file is generated.  The orchestrator sends progress events over SSE or WebSocket connections containing stage, progress and human‑readable messages.  Progress milestones are mapped across the stages: intake (0‑15%), planning (15‑30%), transformation (30‑55%), validation (55‑75%), narration (75‑85%) and completion (100%).

### 🧩 Model Routing (Gemini)
RepoAI dynamically selects large‑language models per agent role through a **Model Router**.  Each role has ordered fallbacks that can be overridden through environment variables.

| Role             | Default Gemini Models → Fallbacks             | Purpose |
|------------------|-----------------------------------------------|---------|
| **INTAKE**       | `gemini-2.5-flash` → `gemini-2.0-flash-exp` → `gemini-2.0-flash` | Fast prompt parsing |
| **PLANNER**      | `gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.0-flash` | Deep reasoning & JSON plan generation |
| **CODER**        | `gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.0-flash` | Code generation and transformation |
| **PR_NARRATOR**  | `gemini-2.5-flash` → `gemini-2.0-flash` → `gemini-2.5-flash-lite` | Summarization and PR narration |
| **EMBEDDING**    | `text-embedding-004` | Lightweight RAG embeddings |

### ⚙️ Configuration via Environment Variables
You can override default models by setting comma‑separated lists in `.env`:

```bash
GOOGLE_API_KEY=your_API_key_here

MODEL_ROUTE_INTAKE="gemini-2.5-flash,gemini-2.0-flash-exp,gemini-2.0-flash"
MODEL_ROUTE_PLANNER="gemini-2.5-pro,gemini-2.5-flash,gemini-2.0-flash"
MODEL_ROUTE_CODER="gemini-2.5-pro,gemini-2.5-flash,gemini-2.0-flash"
MODEL_ROUTE_PR="gemini-2.5-flash,gemini-2.0-flash,gemini-2.5-flash-lite"
EMBEDDING_MODEL="text-embedding-004"

GEMINI_DEFAULT_TIMEOUT_S=60
GEMINI_MAX_RETRIES=2
