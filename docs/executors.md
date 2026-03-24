---
title: Executors
description: HexClamp executor reference
---

# Executors

Executors are the specialist workers of HexClamp. Each one handles a specific category of action. They are selected by the planner based on action type and configuration.

---

## Overview

| Executor | Action type | Evidence required | Default |
|----------|-------------|-------------------|---------|
| `research` | `research` | No | ✅ Enabled |
| `code` | `code` | Yes (`py_compile`) | ❌ Disabled |
| `browser` | `browser` | Yes | ❌ Disabled |
| `messaging` | `messaging` | Yes | ❌ Disabled |
| `system` | — | — | ❌ Removed |

Evidence requirements are enforced by the `Verifier`. If an executor in `verification.required_for` is used without evidence, the result is marked `verified: False`.

---

## Research Executor

**Action type:** `research`

Produces grounded, text-based analysis from input text. Results are appended to `state/recent_changes.md`.

**What it does:**
1. Analyses the input event text or open loop description
2. Generates a structured summary with findings
3. Appends the summary to `state/recent_changes.md` as a markdown log entry
4. Returns evidence pointing to the log file

**Typical use case:** Fact-checking, summarisation, investigation of a topic.

**Output artifacts:** `state/recent_changes.md`

---

## Code Executor

**Action type:** `code`

Delegates code changes to a coding agent in the target workspace.

**What it does:**
1. Reads the current open loop or event
2. Generates a coding brief (goal, files to change, success criteria)
3. Executes the brief in the target workspace
4. Runs `py_compile` on all modified `.py` files as a quality gate
5. Collects evidence (modified file paths, compilation results)

**Evidence:** The executor runs `py_compile` on every modified `.py` file. Syntax errors are recorded as `py_compile:fail:<file>` evidence.

**Typical use case:** Modifying source files, adding tests, refactoring.

**⚠️ Enable only after review:** Code execution can modify files. Make sure your workspace is a git repo with a clean working directory before enabling.

---

## Browser Executor

**Action type:** `browser`

Uses Playwright headless Chromium to navigate web pages, extract text, and capture screenshots.

**What it does:**
1. Launches a headless Chromium browser via Playwright
2. Navigates to the specified URL (from action inputs)
3. Extracts visible text or takes a screenshot
4. Saves artifacts to `state/artifacts/` or `state/runs/`
5. Returns evidence with the URL visited and artifact paths

**Evidence:** URL visited, screenshot paths, extracted text snippets.

**Typical use case:** Scraping web content, verifying a page renders correctly, taking screenshots for reports.

**Prerequisites:**
```bash
pip install playwright
playwright install chromium
```

**Enable in both configs:**
```yaml
# config/agents.yaml
executors:
  browser:
    enabled: true

# config/policies.yaml
executors:
  browser:
    enabled: true
```

---

## Messaging Executor

**Action type:** `messaging`

Sends messages via the Telegram Bot API.

**What it does:**
1. Drafts a message based on the action goal
2. If `external_send.require_approval: true` in `policies.yaml`, writes a sentinel file to `state/messaging_tasks/<task_id>/pending` instead of sending immediately
3. Operator approves via `/approve <task_id>` from Telegram
4. On approval, the message is sent to the configured chat

**Sentinel workflow:**
```
Loop creates pending task → Operator approves → Message sent
```

**Error handling:** Handles Telegram API errors gracefully:
- `403` — Bot was blocked by the user
- `400` — Invalid request (bad chat ID, etc.)
- `429` — Rate limited (retries with backoff)

**Typical use case:** Reporting loop status to an operator, sending summaries to a channel.

**Enable:**
```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
export TELEGRAM_AUTHORIZED_USER_IDS="123456789"
```

---

## Adding a Custom Executor

To add a new executor (e.g., `slack`):

### Step 1 — Implement the executor

Create `agents/executors/slack.py`:

```python
from agents.models import Action, OpenLoop, Result

def execute_slack_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list, list, OpenLoop]:
    # Do the work...
    summary = "Slack message sent"
    evidence = ["slack:channel:#general:posted"]
    artifacts = []
    updated_loop = loop
    return summary, evidence, artifacts, updated_loop
```

### Step 2 — Register in `__init__.py`

```python
from agents.executors.slack import execute_slack_for_loop, execute_slack_for_event
```

### Step 3 — Add action type to schema

In `schemas/action.schema.json`, add `"slack"` to the `type` enum.

### Step 4 — Add executor to config

```yaml
# config/agents.yaml
executors:
  slack:
    enabled: true
    model: default
    role: send_slack_messages
```

### Step 5 — Route in planner

Update `agents/planner.py` to select the `slack` executor for appropriate action types.

### Step 6 — Add role prompt

Create `prompts/executors/slack.md` with the executor's role prompt.

### Step 7 — Add verification requirement (if needed)

In `config/policies.yaml`:

```yaml
verification:
  required_for:
    - code
    - browser
    - messaging
    - slack
```

### Step 8 — Add tests

Add tests in `tests/test_slack_executor.py` or equivalent.

---

## Executor Contracts

All executors must follow this contract:

```python
# For event-driven actions:
def execute_<name>_for_event(action, event) -> tuple[summary, evidence, artifacts, updated_loop]

# For loop-driven actions:
def execute_<name>_for_loop(action, loop) -> tuple[summary, evidence, artifacts, updated_loop]
```

Return values:
- **`summary`** — Human-readable description of what was done
- **`evidence`** — List of proof items (file paths, URLs, status strings)
- **`artifacts`** — List of files produced
- **`updated_loop`** — The `OpenLoop` with updated status/evidence
