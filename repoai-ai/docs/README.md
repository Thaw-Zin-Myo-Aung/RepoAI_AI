# Documentation

RepoAI documentation and guides.

## Quick Links

- API Documentation – Run the server and visit `/docs` in your browser to see the interactive API docs.
- [Tests README](../tests/README.md) - How to run tests
- [Scripts README](../scripts/README.md) - Available utility scripts

## Architecture Overview

Below is an ASCII diagram using box characters and arrows to illustrate how components in RepoAI interact.  It is followed by key features, pipeline details and a note about upcoming RAG integration.

RepoAI Architecture
===================
```
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
│  (Google Gemini)    │
└─────────────────────┘
```

* **Java Backend (Spring)** – Accepts user requests and forwards them to the Python service.  It also relays streaming events and confirmation prompts back to the user.
* **FastAPI API Layer** – Exposes endpoints to start refactor jobs, check status and send confirmations.  Supports Server‑Sent Events (SSE) and WebSocket connections for real‑time streaming.
* **Orchestrator** – Coordinates the pipeline of agents.  The `OrchestratorAgent` runs in fully autonomous mode, while the `ChatOrchestrator` inserts confirmation checkpoints and interprets natural‑language responses.
* **Specialised Agents** – Five agents handle distinct tasks: parsing the prompt (Intake), generating a plan (Planner), applying code changes (Transformer), validating the result (Validator) and crafting a PR description (PR Narrator).
* **LLM Provider** – Uses role‑specific Gemini models via a Pydantic adapter; each agent calls the LLM to produce structured outputs.

### Key Features & Design Choices

* **JST/AST‑based context extraction** – To avoid sending entire source files to the language model, RepoAI leverages a Java Abstract Syntax Tree (AST) parser built on `javalang`.  The `extract_relevant_context` utility analyses large files and returns only the package statement, imports, class structure and methods or annotations relevant to the user’s intent.  This targeted context extraction reduces token usage and ensures the LLM focuses on the most pertinent code when generating plans and transformations.

* **Server‑Sent Events (SSE) streaming** – The FastAPI layer supports SSE, enabling real‑time streaming of progress and build output.  The orchestrator reports progress percentages for each stage (e.g., intake, planning, transformation) and streams file‑by‑file changes or compilation logs so users can monitor progress without waiting for the entire job to finish.  WebSocket support is also available but SSE is the primary mechanism for streaming.

* **Deep code analysis in planning and transformation** – Both the Planner and Transformer agents analyse the repository’s existing code to align generated changes with the current implementation.  The Planner agent assesses refactoring requirements, dependencies and risks to produce a structured `RefactorPlan`.  The Transformer agent uses tools like `get_file_context` and `analyze_java_class` to read the AST of target classes, extract method signatures and annotations, and ensure that generated code matches existing conventions and architectures.

* **LLM‑powered reasoning and confirmations** – The Orchestrator doesn’t just chain agents; it uses large‑language‑model reasoning to interpret user responses, decide on retry strategies after validation failures and mediate interactive checkpoints.  In interactive mode, users can approve or modify plans using natural language, and an LLM interprets their intent and confidence to produce an `OrchestratorDecision` with actions such as `approve_plan`, `request_changes` or `abort`.

* **Progress tracking and checkpointing** – Each stage of the pipeline is mapped to a progress range (e.g., 0–15 % for intake) and can emit `requires_confirmation` flags.  This allows the client to display a progress bar and to pause execution at checkpoints for plan and push confirmations.  Retry logic automatically re‑runs failed stages in autonomous mode, while interactive sessions wait for user input.

### Pipeline Execution & Progress

During a refactor session, the orchestrator executes each agent in sequence.  Progress is reported in ranges so that clients can display a consistent progress bar and know when confirmations are required:


* **Intake (0–15 %)** – Parse the natural‑language prompt, select relevant files and set initial metadata.
* **Planning (15–30 %)** – Generate a detailed `RefactorPlan` with risk levels and dependencies.  In interactive modes, the plan is summarised and sent to the user for approval.
* **Transformation (30–55 %)** – Apply code changes.  Supports batch mode (all changes at once) or streaming mode (file‑by‑file updates with SSE events).  May request confirmation before moving to validation.
* **Validation (55–75 %)** – Compile and test the project, run static analysis and security checks.  Build output and test logs are streamed back line‑by‑line.
* **Narration (75–85 %)** – Compose a human‑readable pull‑request description summarising changes, rationale and test results.  Final confirmation may be requested before pushing.
* **Completion (85–100 %)** – Commit and push changes to a new branch, create a PR and send the final result back to the backend.

Interactive modes insert checkpoints after planning and before pushing so users can approve, modify or abort the process.  Autonomous mode runs the entire pipeline without intervention, retrying failed validations according to predefined logic.

### Future Improvement: Retrieval‑Augmented Generation (RAG)

The current implementation relies on AST parsing and internal analysis to provide context to the language model.  A planned enhancement is to integrate **retrieval‑augmented generation (RAG)** so that the AI service can access a broader repository context without exceeding model limits.  The idea is to index repository files into a vector database (e.g., Qdrant) and expose API endpoints for searching and embedding.  During planning, the orchestrator will send the user’s prompt and repository ID to the backend’s RAG service to retrieve the top‑K most relevant code snippets.  These snippets will then be concatenated as additional context for the Planner and Transformer agents.

Implementing RAG will require:

1. **Embedding generation** – A new `/embeddings/encode` endpoint in the AI service will use Gemini’s `text‑embedding‑004` model to generate vectors for code chunks.  The backend will call this endpoint when indexing repositories.
2. **RAG search endpoint** – The backend will provide a `POST /api/rag/search-for-ai` API that returns top‑K relevant code snippets given a prompt and repository ID.
3. **Planner integration** – The Planner agent will call the RAG search endpoint before generating a plan.  Retrieved code snippets will be appended to the system prompt as additional context, improving the quality and relevance of the refactoring plan.  Subsequent agents may also leverage the retrieved context when available.

This RAG integration will enhance the AI’s awareness of existing design patterns, naming conventions and code style across the repository, leading to better‑aligned refactoring recommendations.

## AI Implementation Pipeline

While the architecture diagram above shows the end‑to‑end flow from the backend to the LLM provider, it is also useful to visualise the **AI implementation pipeline** itself.  The pipeline transforms a natural‑language request into a validated set of code changes and a polished PR description.  Each stage uses a dedicated agent powered by Gemini models and domain‑specific tools.

AI Implementation Pipeline
==========================

```
┌──────────────┐
│ Intake Agent │
│ (LLM + tools │
│  for file    │
│  listing &   │
│  AST context)│
└──────┬───────┘
       │ produces **JobSpec** describing
       │ the requested refactor
       ▼
┌────────────────┐
│ Planner Agent  │
│ (LLM + risk &  │
│  dependency    │
│  analysis)     │
└──────┬─────────┘
       │ produces **RefactorPlan** with
       │ ordered steps, durations & risks
       ▼
┌─────────────────────┐
│ Transformer Agent   │
│ (LLM + AST analysis │
│  & code generation  │
│  tools; batch or    │
│  streaming mode)    │
└──────┬──────────────┘
       │ produces **CodeChange** objects,
       │ file‑by‑file if streaming
       ▼
┌──────────────────┐
│ Validator Agent  │
│ (Compilation,    │
│  test execution, │
│  static analysis)│
└──────┬───────────┘
       │ produces **ValidationResult** with
       │ pass/fail, coverage & confidence
       ▼
┌──────────────┐
│ PR Narrator  │
│ Agent        │
└──────────────┘
       │ produces a human‑readable PR
       │ description summarising changes
       │ and test results
       ▼
┌──────────────────┐
│ Orchestrator     │
│ Decision Logic   │
└──────────────────┘
       │ interacts with user via SSE/
       │ WebSocket for confirmations and
       │ decides on retries or aborts
```

This diagram emphasises how each agent contributes to transforming the original prompt into a safe, high‑quality refactoring.  The orchestrator coordinates these agents, streams progress events to the client, and invokes confirmations at key checkpoints.
