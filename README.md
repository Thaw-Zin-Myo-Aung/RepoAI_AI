# 🧠 RepoAI – AI Service Overview

This is the intelligent core of RepoAI.  
It receives user prompts and repository access data from the backend API, orchestrates specialized AI agents powered by multiple AIML models, and returns validated, refactored code with supporting evidence.

---

## 🚀 How It Works

### 1️⃣ Request Intake
The backend (Spring Boot) sends a POST request to the AI service containing:
- **User Prompt** – what refactor or analysis to perform  
- **GitHub Credentials** – repo access token and metadata  
- **Optional Scope** – specific file paths, branch, or constraints  

The AI service initializes a session and triggers an orchestrated agent workflow.

### 2️⃣ Agentic Workflow
Each agent is modular, allowing independent testing and replacement.  
The main agents in the pipeline are:

| Agent | Role | Description |
|--------|------|-------------|
| **Intake Agent** | Chat Parsing | Interprets user prompt, identifies intent, and creates a structured `JobSpec`. |
| **Planner Agent** | Orchestration | Uses reasoning models to draft a `RefactorPlan` informed by repository context and RAG retrieval. |
| **Transformer Agent** | Code Refactoring | Applies deterministic codemods and uses code-optimized models for semantic edits. |
| **Validator Agent** | Quality Assurance | Runs static analysis, linters, and unit tests to validate generated patches. |
| **PR Narrator Agent** | Documentation | Summarizes diffs and evidence into a human-readable PR description. |
| **Policy Gate** | Safety Check | Verifies branch protection, change size, and non-destructive updates. |

---

## 🧩 Model Routing (Gemini)

RepoAI dynamically selects models per agent role through a **Model Router**.  
Each role has ordered fallbacks that can be overridden through environment variables.

| Role | Default AIML Models (Primary → Fallbacks) | Purpose |
|------|-------------------------------------------|----------|
| **INTAKE** | `gemini-2.0-flash-thinking-exp-01-21` → `gemini-2.0-flash-exp` → `gemini-1.5-flash-002` | Fast reasoning for parsing user prompts |
| **PLANNER** | `gemini-2.0-flash-thinking-exp-01-21` → `gemini-exp-1206` → `gemini-2.5-pro-exp-03-04` | Deep reasoning & JSON plan generation |
| **PR_NARRATOR** | `gemini-2.0-flash-exp` → `gemini-1.5-flash-002` → `gemini-2.0-flash-thinking-exp-01-21` | PR summarization and rationale |
| **CODER** | `gemini-2.5-pro-exp-03-04` → `gemini-exp-1206` → `gemini-2.0-flash-thinking-exp-01-21` | Code refactoring and completions |
| **EMBEDDING** | `text-embedding-004` | Lightweight RAG embeddings (Gemini) |

---

### ⚙️ Configurable via Environment Variables

You can override any defaults in `.env` using comma-separated lists.  
The router will use them in the order given (first = primary).

```bash
GOOGLE_API_KEY=your_API_key_here

MODEL_ROUTE_INTAKE="gemini-2.0-flash-thinking-exp-01-21,gemini-2.0-flash-exp,gemini-1.5-flash-002"
MODEL_ROUTE_PLANNER="gemini-2.0-flash-thinking-exp-01-21,gemini-exp-1206,gemini-2.5-pro-exp-03-04"
MODEL_ROUTE_CODER="gemini-2.5-pro-exp-03-04,gemini-exp-1206,gemini-2.0-flash-thinking-exp-01-21"
MODEL_ROUTE_PR="gemini-2.0-flash-exp,gemini-1.5-flash-002,gemini-2.0-flash-thinking-exp-01-21"
EMBEDDING_MODEL="text-embedding-004"

GEMINI_DEFAULT_TIMEOUT_S=60
GEMINI_MAX_RETRIES=2
