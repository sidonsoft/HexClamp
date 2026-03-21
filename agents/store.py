from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parents[1]
STATE_DIR = BASE / "state"
RUNS_DIR = BASE / "runs"
SCHEMAS_DIR = BASE / "schemas"


RUNTIME_JSON_DEFAULTS = {
    STATE_DIR / "current_state.json": {
        "goal": "Keep hydra-claw-loop coherent and progressing",
        "active_context": [],
        "recent_events": [],
        "current_actions": [],
        "open_loops": [],
        "last_verified_result": None,
    },
    STATE_DIR / "event_queue.json": [],
    STATE_DIR / "open_loops.json": [],
}

RUNTIME_TEXT_DEFAULTS = {
    STATE_DIR / "recent_changes.md": "# Recent Changes\n\n",
}


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def bootstrap_runtime_state() -> list[str]:
    """Create any missing runtime files with safe defaults."""
    ensure_dirs()
    created: list[str] = []

    for path, default in RUNTIME_JSON_DEFAULTS.items():
        if not path.exists():
            write_json(path, default)
            created.append(str(path.relative_to(BASE)))

    for path, default in RUNTIME_TEXT_DEFAULTS.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default, encoding="utf-8")
            created.append(str(path.relative_to(BASE)))

    return created


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """Atomic JSON write: write to temp file then rename to target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory (same filesystem for atomic rename)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        # Atomic rename (on POSIX systems)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def append_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + text, encoding="utf-8")


def append_json_array(path: Path, item: Any) -> list[Any]:
    """Append item to JSON array atomically using read-modify-write with atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # read_json + append + write_json (atomic rename) is sufficient
    # since write_json uses temp file + os.replace (atomic on POSIX)
    data = read_json(path, default=[])
    data.append(item)
    write_json(path, data)
    return data
