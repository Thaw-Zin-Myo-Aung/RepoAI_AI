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

## 🧩 Model Routing (AIML API)

RepoAI dynamically selects models per agent role through a **Model Router**.  
Each role has ordered fallbacks that can be overridden through environment variables.

| Role | Default AIML Models (Primary → Fallbacks) | Purpose |
|------|-------------------------------------------|----------|
| **INTAKE** | `deepseek/deepseek-chat-v3.1` → `alibaba/qwen-max` → `claude-sonnet-4-5-20250929` | Fast reasoning for parsing user prompts |
| **PLANNER** | `deepseek/deepseek-reasoner-v3.1` → `alibaba/qwen3-next-80b-a3b-thinking` → `claude-opus-4-20250514` | Deep reasoning & JSON plan generation |
| **PR_NARRATOR** | `deepseek/deepseek-chat-v3.1` → `claude-haiku-4-5-20251001` → `alibaba/qwen3-235b-a22b-thinking-2507` | PR summarization and rationale |
| **CODER** | `alibaba/qwen3-coder-480b-a35b-instruct` → `Qwen/Qwen2.5-Coder-32B-Instruct` → `deepseek/deepseek-chat-v3.1` → `claude-opus-4-1-20250805` | Code refactoring and completions |
| **EMBEDDING** | `bge-small` | Lightweight RAG embeddings |

---

### ⚙️ Configurable via Environment Variables

You can override any defaults in `.env` using comma-separated lists.  
The router will use them in the order given (first = primary).

```bash
AIMLAPI_BASE_URL=https://api.aimlapi.com/v1
AIMLAPI_KEY=your_api_key_here

MODEL_ROUTE_INTAKE="deepseek/deepseek-chat-v3.1,alibaba/qwen-max,claude-sonnet-4-5-20250929"
MODEL_ROUTE_PLANNER="deepseek/deepseek-reasoner-v3.1,alibaba/qwen3-next-80b-a3b-thinking,claude-opus-4-20250514"
MODEL_ROUTE_PR="deepseek/deepseek-chat-v3.1,claude-haiku-4-5-20251001,alibaba/qwen3-235b-a22b-thinking-2507"
MODEL_ROUTE_CODER="alibaba/qwen3-coder-480b-a35b-instruct,Qwen/Qwen2.5-Coder-32B-Instruct,deepseek/deepseek-chat-v3.1,claude-opus-4-1-20250805"
EMBEDDING_MODEL="bge-small"

AIML_DEFAULT_TIMEOUT_S=45
AIML_MAX_RETRIES=2
