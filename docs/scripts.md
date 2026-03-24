---
title: Scripts
description: HexClamp utility scripts reference
---

# Scripts

The `scripts/` directory contains standalone utilities that support the HexClamp runtime. They are not part of the core loop but are called by it or used independently by operators.

---

## bootstrap_runtime.py

**Purpose:** Bootstrap the initial HexClamp runtime state.

Creates the `state/` directory structure, all required JSON files (`current_state.json`, `event_queue.json`, `open_loops.json`, etc.), and the `runs/` subdirectory.

**Usage:**
```bash
python scripts/bootstrap_runtime.py
```

This is also called internally by `python3 -m agents.loop init`.

**Key behaviour:**
- If state files already exist, it does not overwrite them (idempotent).
- Sets the initial `goal` to `"Keep hexclamp coherent and progressing"`.
- Creates `state/circuit_breaker.json` with `{"open": false, "consecutive_errors": 0}`.

---

## browser_executor.py

**Purpose:** Playwright-based browser automation for the `browser` executor.

Wraps Playwright's headless Chromium to:
- Navigate to a URL
- Extract visible text content
- Capture screenshots
- Return structured results (URL, text, screenshot paths)

**Usage:**
```bash
python scripts/browser_executor.py <url> [--screenshot]
```

**Called by:** The `browser` executor in `agents/executors/browser.py`.

**Key behaviour:**
- Launches Chromium in headless mode
- Navigates to the target URL
- Extracts `document.body.innerText` as the page text
- Optionally saves a screenshot to `state/artifacts/`
- Returns evidence: URL visited, screenshot path, text length

---

## browser_runner.py

**Purpose:** Higher-level Playwright orchestration script.

Manages browser sessions for the browser executor, handling:
- Browser launch and teardown
- Cookie/session management
- Multiple navigation steps in a single session

**Called by:** `browser_executor.py` or directly by `agents/executors/browser.py`.

**Key behaviour:**
- Manages a Playwright browser context across multiple actions
- Handles timeouts and navigation errors gracefully
- Cleans up browser resources on exit

---

## browser_task.py

**Purpose:** Single browser task entry point.

A thin wrapper that takes a task description and URL, runs the browser, and writes results to a designated output path.

**Usage:**
```bash
python scripts/browser_task.py <task-id> <url> [--output path/to/result.json]
```

**Key behaviour:**
- Runs a single browser task (navigate + extract/screenshot)
- Writes result JSON to the specified output path
- Used by the loop to track individual browser tasks independently

---

## approve_message.py

**Purpose:** Manually approve a pending messaging task (alternative to Telegram `/approve` command).

**Usage:**
```bash
python scripts/approve_message.py <task-id>
```

**Key behaviour:**
- Touches the `approved` sentinel file in `state/messaging_tasks/<task-id>/`
- If the task is not in a `pending` state, exits with an error
- Used when the operator prefers CLI to Telegram for approvals

**Note:** This does not bypass `TELEGRAM_AUTHORIZED_USER_IDS` — the caller must still be authorised.

---

## edit_toolkit.py

**Purpose:** Shared file-editing utilities used by the `code` executor.

Provides functions for safely editing source files:
- Reading and parsing files
- Applying targeted changes (line-based or AST-based)
- Backing up files before mutation
- Validating edits (e.g., `py_compile` check after edit)

**Used by:** `agents/executors/code_executor.py`

**Key functions:**
```python
def edit_file(path: str, old: str, new: str) -> bool:
    """Replace old text with new text in a file."""

def backup_file(path: str) -> str:
    """Create a .bak backup of the file."""

def validate_python(file_path: str) -> tuple[bool, str]:
    """Run py_compile and return (passed, message)."""
```

---

## loop_intelligence.py

**Purpose:** Analysis and insight generation over the loop's history.

Reads `state/runs/*.json` and `state/recent_changes.md` to produce:
- Activity summaries (actions per day, most common executor, etc.)
- Loop health metrics (error rate, verification success rate, idle cycle ratio)
- Operator digests (formatted summaries for human review)

**Usage:**
```bash
python scripts/loop_intelligence.py --days 7
```

**Output:** Structured JSON or formatted text report of loop performance and activity.

---

## task_completion.py

**Purpose:** Determine whether an open loop has been completed based on artifacts and evidence.

**Usage:**
```bash
python scripts/task_completion.py <loop-id>
```

**Key behaviour:**
- Reads the open loop's `evidence` and `artifacts` fields
- Checks whether required artifacts exist on disk
- Returns a structured result: `{ "complete": true/false, "reason": "..." }`

**Used by:** The verifier and loop intelligence to determine when a loop can be marked `resolved`.

---

## Summary Table

| Script | Purpose | Called by |
|--------|---------|-----------|
| `bootstrap_runtime.py` | Create initial state files | `agents.loop init`, `process_once()` |
| `browser_executor.py` | Playwright navigation + extraction | `agents/executors/browser.py` |
| `browser_runner.py` | Browser session management | `browser_executor.py` |
| `browser_task.py` | Single browser task runner | Loop / CLI |
| `approve_message.py` | CLI message approval | Operator CLI |
| `edit_toolkit.py` | Safe file editing for code executor | `code_executor.py` |
| `loop_intelligence.py` | Analyse loop history and health | Operator / slow loop |
| `task_completion.py` | Determine if a loop is complete | Verifier / planner |
