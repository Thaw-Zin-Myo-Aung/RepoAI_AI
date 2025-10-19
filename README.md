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
This enables flexibility and fallback options when switching between AIML models.

| Role | Example AIML Models | Purpose |
|------|----------------------|----------|
| **INTAKE** | DeepSeek V3.1 → Qwen Max → Qwen Turbo | Chat understanding and task parsing |
| **PLANNER** | DeepSeek Reasoner V3.1 → Qwen QwQ-32B → Qwen Max | Reasoning and structured plan generation |
| **CODER** | Qwen 2.5 72B Instruct Turbo → Qwen 2.5 7B Instruct Turbo → DeepSeek V3.2 Exp Non-thinking | Code transformation and synthesis |
| **PR_NARRATOR** | DeepSeek V3 → Qwen Max → Qwen Turbo | PR summarization and explanation |
| **EMBEDDING** | bge-small (local) | Context retrieval for RAG |

All routes are defined in environment variables, e.g.:

```bash
MODEL_ROUTE_PLANNER="deepseek-reasoner-v3.1,qwq-32b,qwen-max"
MODEL_ROUTE_CODER="qwen2.5-72b-instruct-turbo,qwen2.5-7b-instruct-turbo,deepseek-v3.2-exp-non-thinking"
