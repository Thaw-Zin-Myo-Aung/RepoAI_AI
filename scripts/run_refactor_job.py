#!/usr/bin/env python3
"""
Run a refactor job through the OrchestratorAgent for a local repository.
Usage: run in project root with the virtualenv activated.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from repoai.dependencies import OrchestratorDependencies
from repoai.orchestrator.orchestrator_agent import OrchestratorAgent


def send_message(msg: str) -> None:
    print("[send_message]", msg)


async def main() -> int:
    repo_path = "/home/timmy/RepoAI/RepoAI_AI/cloned_repos/repoai-java-simple-library"
    if not Path(repo_path).exists():
        print(f"ERROR: repository path not found: {repo_path}")
        return 2

    prompt = (
        "Refactor the com.example.library.BookService class in this repository to improve encapsulation and clarity while preserving behaviour.\n\n"
        "Goals:\n"
        "1) Hide the internal books list:\n"
        "   - Change the `books` field from public to private.\n"
        "   - Ensure getAllBooks() returns an unmodifiable copy instead of the internal mutable list.\n\n"
        "2) Split the addBook logic into smaller helpers:\n"
        "   - Extract validation into private methods (validateTitle, validateAuthor, validateYear).\n"
        "   - Extract the duplicate-title check into its own method.\n\n"
        "3) Make the maxBooks rule configurable:\n"
        "   - Allow configuring maxBooks via a constructor argument or setter.\n\n"
        "4) Improve API surface:\n"
        "   - Remove System.out.println and return clearer results or throw structured exceptions.\n\n"
        "Update or add tests in BookServiceTest to cover:\n"
        "- Successful book creation\n"
        "- Duplicate title prevention\n"
        "- Invalid inputs (empty title/author, negative year)\n"
        "- New behaviour of getAllBooks() (should return unmodifiable copy)\n\n"
        "Keep the project buildable with Maven and Java 17.\n"
    )

    deps = OrchestratorDependencies(
        user_id="timmy",
        session_id="refactor_bookservice_001",
        repository_path=repo_path,
        auto_fix_enabled=True,
        max_retries=5,
        enable_progress_updates=True,
        send_message=send_message,
        transformer_batch_size=2,
        transformer_max_tokens=4096,
    )

    orchestrator = OrchestratorAgent(deps)

    print("Starting refactor pipeline...")
    state = await orchestrator.run(prompt)

    print("Pipeline finished. Summary:")
    try:
        state_dict = asdict(state)
    except Exception:
        # Fallback: convert some important fields manually
        state_dict = {
            "session_id": state.session_id,
            "stage": str(state.stage),
            "status": str(state.status),
            "errors": state.errors,
        }
    print(json.dumps(state_dict, indent=2, default=str))

    if state.status.name == "COMPLETED":
        print("Refactor pipeline completed successfully")
        return 0
    else:
        print("Refactor pipeline did not complete successfully")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
