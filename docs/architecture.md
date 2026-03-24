---
title: Architecture
description: HexClamp architecture overview
---

# Architecture

HexClamp is structured as a Python package under `agents/`, with configuration in `config/`, schemas in `schemas/`, prompts in `prompts/`, state in `state/`, and utility scripts in `scripts/`.

---

## Directory Structure

```
HexClamp/
├── agents/
│   ├── __init__.py
│   ├── loop.py          # Main entry point: O→C→P→E→V→P cycle
│   ├── models.py        # Dataclasses: Event, Action, OpenLoop, Result, CurrentState
│   ├── observer.py      # Normalize raw inputs into Events
│   ├── condenser.py     # Compress events + loops into CurrentState
│   ├── planner.py       # Rank open loops, select next actions
│   ├── verifier.py      # Validate claimed results against evidence
│   ├── store.py         # Atomic JSON file I/O utilities
│   ├── validate.py      # JSON Schema validation with caching
│   ├── condenser.py
│   ├── delivery.py      # TelegramDeliveryAgent (polling + sending)
│   └── executors/
│       ├── __init__.py      # Public executor exports
│       ├── base.py          # Shared helpers, quality gates, policies
│       ├── browser.py       # Playwright headless Chromium executor
│       ├── code_executor.py # Code execution executor
│       ├── messaging.py    # Telegram messaging executor
│       └── research.py     # Research / summarisation executor
│
├── config/
│   ├── agents.yaml      # Model routing and executor toggle
│   ├── loops.yaml       # Loop priority and scheduling
│   └── policies.yaml    # Verification gates and loop control
│
├── schemas/
│   ├── event.schema.json
│   ├── action.schema.json
│   ├── loop.schema.json
│   ├── result.schema.json
│   └── state.schema.json
│
├── prompts/
│   ├── observer.md       # Role prompt for the observer
│   ├── condenser.md     # Role prompt for the condenser
│   ├── planner.md       # Role prompt for the planner
│   ├── verifier.md       # Role prompt for the verifier
│   └── executors/
│       ├── research.md
│       ├── code.md
│       ├── browser.md
│       └── messaging.md
│
├── scripts/
│   ├── bootstrap_runtime.py
│   ├── browser_executor.py
│   ├── browser_runner.py
│   ├── browser_task.py
│   ├── approve_message.py
│   ├── edit_toolkit.py
│   ├── loop_intelligence.py
│   └── task_completion.py
│
└── state/
    ├── current_state.json    # Condensed state
    ├── event_queue.json      # Pending events
    ├── open_loops.json       # Active tasks
    ├── polling_state.json    # Telegram offset
    ├── circuit_breaker.json  # Error circuit breaker
    ├── recent_changes.md     # Audit log
    └── runs/
        ├── last_run.json
        └── run-TIMESTAMP.json
```

---

## Core Modules

### `agents/models.py`
Defines the five fundamental dataclasses:

| Class | Purpose |
|-------|---------|
| `Event` | A normalised input — message, poll result, etc. |
| `Action` | A planned step with executor, goal, success criteria, and risk level |
| `OpenLoop` | A named task with status (`open`, `blocked`, `resolved`), owner, and evidence |
| `Result` | Outcome of execution: summary, evidence, artifacts, and `verified` flag |
| `CurrentState` | The condensed snapshot passed to the planner each cycle |

### `agents/loop.py`
The main cycle engine. Implements the O→C→P→E→V→P loop in `process_once()`:

1. Load event queue and open loops from disk
2. Condense state
3. Plan next actions
4. Execute the top action
5. Verify the result
6. Persist updated state

Also exposes CLI commands: `init`, `enqueue`, `poll`, `status`.

### `agents/observer.py`
Normalises raw inputs into structured `Event` objects. Raw text becomes a `chat_message` event with a `payload.text` field.

### `agents/condenser.py`
Compresses the event queue and open loops into a focused `CurrentState`. This is what the planner uses — it never sees the raw event history.

### `agents/planner.py`
Ranks open loops by urgency and selects the most important action. Handles stale loop pruning (loops older than `STALE_THRESHOLD_HOURS` are dropped).

### `agents/verifier.py`
Checks claimed results against evidence. If an action type is in `verification.required_for` in `policies.yaml`, evidence must be present for the result to be marked `verified`.

### `agents/store.py`
Atomic JSON file I/O: `read_json`, `write_json`, `append_json_array`, `append_markdown`. All state writes are atomic to prevent corruption on crash.

### `agents/validate.py`
JSON Schema validation with caching. Schemas are loaded once and reused across validation calls.

### `agents/delivery.py`
The `TelegramDeliveryAgent` handles both polling (fetching new messages) and delivery (sending messages via the Bot API).

---

## Data Flow

```
Raw Input (CLI / Telegram poll)
        │
        ▼
  ┌───────────┐
  │ Observer  │  → Event (normalised, schema-validated)
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │ Condenser │  → CurrentState (compressed context)
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │  Planner  │  → Action[] (ranked, selected)
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │ Executor  │  → Result (summary, evidence, artifacts)
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │ Verifier  │  → Result (verified: true/false)
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │   Store   │  → JSON files on disk
  └───────────┘
```

---

## State Files

| File | Format | Purpose |
|------|--------|---------|
| `current_state.json` | JSON | Condensed system state |
| `event_queue.json` | JSON array | Pending events |
| `open_loops.json` | JSON array | Active tasks |
| `polling_state.json` | JSON | Telegram polling offset |
| `circuit_breaker.json` | JSON | Error tracking |
| `recent_changes.md` | Markdown | Append-only action log |
| `runs/last_run.json` | JSON | Most recent cycle trace |
| `runs/run-TIMESTAMP.json` | JSON | Historical cycle traces |

---

## Security Notes

- The `system` executor has been removed — there is no back-door execution branch.
- Messaging tasks require approval unless `require_approval: false` is set in `policies.yaml`.
- `TELEGRAM_AUTHORIZED_USER_IDS` is the only allowlist; unauthorized callers cannot trigger approvals.
- Configuration files are read-only from the loop's perspective; no self-modification.
