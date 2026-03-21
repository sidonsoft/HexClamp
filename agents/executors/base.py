from __future__ import annotations

import sys
import subprocess
import yaml
from pathlib import Path
from datetime import datetime, timezone

from models import Action, Event, OpenLoop
from store import append_markdown, write_json
import store

BASE = store.BASE  # Re-export for patching

STALE_EVIDENCE_THRESHOLD = 3
_policies_cache: dict | None = None


def _write_change(action: Action, summary: str) -> str:
    artifact = store.BASE / "state" / "recent_changes.md"
    append_markdown(artifact, f"- {action.id}: {summary}\n")
    return str(Path("state/recent_changes.md"))


def _initial_loop_state(event: Event, owner: str) -> tuple[str, str, list[str], str]:
    text = event.payload.get("text", "")
    normalized = text.lower()

    if "done" in normalized or "resolved" in normalized:
        return (
            "resolved",
            "No further action required.",
            [],
            f"Observed resolved request: {text}",
        )
    if "blocked" in normalized or "waiting" in normalized:
        return (
            "blocked",
            "Wait for dependency or operator input.",
            ["external dependency"],
            f"Observed blocked request: {text}",
        )
    return (
        "open",
        "Decide whether this item needs deeper execution.",
        [],
        f"Observed request: {text}" if text else f"Observed event {event.id}",
    )


def _load_policies() -> dict:
    """Load policies.yaml if present, cached for the lifetime of the process."""
    global _policies_cache
    if _policies_cache is not None:
        return _policies_cache
    policies_path = store.BASE / "config" / "policies.yaml"
    if policies_path.exists():
        with open(policies_path, "r") as f:
            _policies_cache = yaml.safe_load(f) or {}
    else:
        _policies_cache = {}
    return _policies_cache


def _quality_gate_changed_files(
    changed_files: list[str], workspace_root: Path
) -> tuple[list[str], list[str]]:
    """
    Run py_compile on each changed .py file and collect evidence.
    Returns (syntax_ok_files, syntax_failures).
    """
    evidence = []
    failures = []
    for file_path_str in changed_files:
        if not file_path_str.endswith(".py"):
            continue
        file_path = Path(file_path_str)
        # Try workspace-relative path
        if not file_path.is_absolute():
            file_path = workspace_root / file_path
        if not file_path.exists():
            continue
        passed, msg = _run_python_test(file_path)
        if passed:
            evidence.append(f"py_compile:ok:{file_path.name}")
        else:
            failures.append(f"py_compile:fail:{file_path.name}:{msg}")
            evidence.append(f"py_compile:fail:{file_path.name}")
    return evidence, failures


def _run_python_test(file_path: Path) -> tuple[bool, str]:
    """Run Python file with basic syntax check and return (passed, output)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, f"Syntax check passed for {file_path.name}"
        return False, f"Syntax error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"
    except Exception as e:
        return False, f"Test error: {e}"
