---
title: The Loop
description: Deep dive into the HexClamp O→C→P→E→V→P cycle
---

# The O → C → P → E → V → P Loop

Every invocation of `process_once()` executes one complete HexClamp cycle. This document explains what happens in each stage and how state flows through the system.

---

## Cycle Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         HEXCLAMP CYCLE                          │
│                                                                 │
│   ┌───────┐   ┌──────────┐   ┌────────┐   ┌──────────┐          │
│   │ OBSERVE│ → │ CONDENSE │ → │  PLAN  │ → │ EXECUTE  │          │
│   └───────┘   └──────────┘   └────────┘   └────┬─────┘          │
│                                                  │               │
│                    ┌────────────────────────────┘               │
│                    │                                            │
│                    ▼                                            │
│             ┌──────────┐   ┌──────────┐                         │
│             │ VERIFY   │ → │ PERSIST  │                         │
│             └──────────┘   └──────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 1 — Observe

**Input:** Raw text from CLI `enqueue` or Telegram `poll`
**Output:** Structured `Event` objects in `state/event_queue.json`

The `Observer` normalises raw inputs into typed `Event` records:

```python
class Event:
    id: str              # Unique event ID (e.g., evt_abc123)
    timestamp: str        # ISO 8601 UTC
    source: str           # "cli", "telegram", "poll"
    kind: str             # "chat_message", "system", etc.
    payload: dict         # Normalised content (e.g., {"text": "..."})
    tags: list[str]       # Extracted labels
    priority: str         # "normal" or "high"
```

Key design principle: **raw inputs are normalised before use**. No executor ever sees unprocessed user text.

---

## Stage 2 — Condense

**Input:** Event queue + open loops + previous `CurrentState`
**Output:** New `CurrentState`

The `Condenser` compresses the full event history and task list into a focused snapshot:

```python
class CurrentState:
    goal: str                          # System-level goal
    active_context: list[str]          # Most relevant recent items
    recent_events: list[str]           # Recent event IDs
    current_actions: list[str]         # In-flight action IDs
    open_loops: list[str]              # Active loop IDs
    last_verified_result: dict | None  # Most recent verified result
```

This is the **only context** the planner sees. It never gets the raw event history — only the distilled version.

The condenser also applies loop classification logic: events containing "done" or "resolved" mark loops as `resolved`; "blocked" or "waiting" mark them as `blocked`.

---

## Stage 3 — Plan

**Input:** `CurrentState`, event queue, open loops
**Output:** Ranked `Action[]`

The `Planner` does two things:

1. **Rank open loops** by urgency, age, and status. Stale loops (older than `STALE_THRESHOLD_HOURS`) are pruned.
2. **Select the next action** — the most urgent open loop or the next queued event gets an action plan.

```python
class Action:
    id: str              # Unique action ID
    type: str            # Action type (maps to executor)
    goal: str            # What this action aims to achieve
    inputs: list[str]    # Inputs needed
    executor: str        # Which executor handles this ("research", "code", etc.)
    success_criteria: str # What "done" looks like
    risk: str             # "low", "medium", "high"
    status: str           # "planned", "running", "done", "failed"
```

Routing: the planner selects the executor based on the action type and what is enabled in `config/agents.yaml`.

---

## Stage 4 — Execute

**Input:** `Action` + relevant `Event` or `OpenLoop`
**Output:** `Result` (summary, evidence, artifacts)

The selected executor runs the action:

| Executor | What it does |
|----------|-------------|
| `research` | Analyses input text, produces a grounded summary → `state/recent_changes.md` |
| `code` | Delegates to a coding agent in the target workspace |
| `browser` | Launches Playwright headless Chromium — navigates, extracts text, takes screenshots |
| `messaging` | Sends a Telegram message (sentinel-approval required for external sends) |

Executors have **narrow authority** — each only knows how to do one thing well. They return a `Result`:

```python
class Result:
    action_id: str
    status: str               # "success", "partial", "failed"
    summary: str              # Human-readable outcome
    evidence: list[str]       # Proof of work (file paths, URLs, etc.)
    artifacts: list[str]      # Files produced
    follow_up: list[str]      # Suggested next steps
    verified: bool            # Set by the verifier
```

---

## Stage 5 — Verify

**Input:** `Action`, claimed `Result`
**Output:** `Result` with `verified` flag

The `Verifier` checks the result against evidence:

- If `verification.required_for` includes the executor type (`code`, `browser`, `messaging`), evidence must be present.
- If evidence is missing or unconvincing, the result is marked `verified: False`.
- The event is **left in the queue** if verification fails — it will be retried in the next cycle.

The `code` executor has a built-in quality gate: `py_compile` is run on all modified `.py` files, and syntax failures are recorded as evidence.

---

## Stage 6 — Persist

**Input:** Updated queue, loops, state
**Output:** JSON files on disk

All state is written atomically to `state/`:

- `event_queue.json` — updated event queue
- `open_loops.json` — updated open loops
- `current_state.json` — condensed state
- `recent_changes.md` — append-only action log
- `runs/last_run.json` + `runs/run-TIMESTAMP.json` — cycle trace

File-backed persistence means:
- The loop can be stopped and restarted at any time
- State is fully inspectable — just `cat state/current_state.json`
- No context is ever "invisible" inside a prompt

---

## Circuit Breaker

If three consecutive execution errors occur, the **circuit breaker trips** and the loop halts:

```
CIRCUIT BREAKER TRIPPED — loop halted
```

This prevents runaway error cascades. To reset:

```bash
# Manually clear circuit breaker (edit state/circuit_breaker.json)
# Set: {"open": false, "consecutive_errors": 0}
python3 -m agents.loop  # Will resume on next invocation
```

---

## Idle Cycles

If there is nothing to do (event queue empty, no open loops), the loop enters an **idle cycle**:
- Current actions are cleared
- Stale loops are pruned from `open_loops.json`
- State is persisted
- The loop exits cleanly

This means running HexClamp on a schedule (cron, timer) is safe — idle cycles cost nothing.
