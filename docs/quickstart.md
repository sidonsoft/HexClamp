---
title: Quick Start
description: Get HexClamp running in minutes
---

# Quick Start

This guide walks you through the essential commands to get HexClamp running.

---

## 1. Bootstrap Runtime State

```bash
python3 -m agents.loop init
```

```
{
  "bootstrapped": true
}
```

Creates the `state/` directory and all required JSON files. **Run this once** after a fresh clone or if state is missing.

---

## 2. Enqueue Tasks

Add work to the event queue:

```bash
python3 -m agents.loop enqueue "investigate the auth bug"
python3 -m agents.loop enqueue "review PR #42"
python3 -m agents.loop enqueue "summarise the Q4 metrics report"
```

Each `enqueue` call creates a structured `Event` in `state/event_queue.json`:

```
{
  "queued": {
    "id": "evt_abc123...",
    "timestamp": "2026-01-01T12:00:00Z",
    "source": "cli",
    "kind": "chat_message",
    "payload": { "text": "investigate the auth bug" },
    "tags": [],
    "priority": "normal"
  }
}
```

### Priority

```bash
python3 -m agents.loop enqueue "hotfix critical bug" --priority high
# or inline:
python3 -m agents.loop enqueue "do this first" high
```

---

## 3. Run One Loop Cycle

```bash
python3 -m agents.loop
```

This executes a single **O→C→P→E→V→P** cycle:

1. Loads the event queue and open loops from disk
2. Condenses state
3. Plans the next action
4. Executes it via the appropriate executor
5. Verifies the result
6. Persists updated state

Output is written to `state/runs/last_run.json` and printed to stdout as formatted JSON.

---

## 4. Check System Status

```bash
python3 -m agents.loop status
```

```
=== HexClamp Status ===
Goal: Keep hexclamp coherent and progressing

Queue Size: 1 events
Next in queue:
  - [evt_abc12] investigate the auth bug...

Open Loops: 3
Current priorities:
  1. [OPEN] investigate the auth bug
  2. [OPEN] review PR #42
  3. [OPEN] summarise the Q4 metrics...

Planned Next Action:
  Type: research
  Goal: investigate the auth bug
  Executor: research

========================
```

---

## 5. Poll Telegram for Inbound Messages

If you have the `messaging` executor enabled and `TELEGRAM_BOT_TOKEN` set:

```bash
python3 -m agents.loop poll
```

```
{
  "polled": 5,
  "enqueued": 3,
  "ignored": 2,
  "approvals": 0,
  "new_offset": 42,
  "events": [...]
}
```

| Field | Meaning |
|-------|---------|
| `polled` | Total updates received from the Bot API |
| `enqueued` | Updates normalized as new `Event` records |
| `ignored` | Non-text updates (photos, stickers) safely skipped |
| `approvals` | `/approve <id>` commands processed |
| `new_offset` | Saved to prevent duplicate processing |

---

## 6. Approve a Messaging Task

When a messaging task is pending sentinel approval, an authorized operator can approve it via Telegram:

```
/approve <task-id>
```

> **Requires:** `TELEGRAM_AUTHORIZED_USER_IDS` must include your Telegram user ID.

---

## Running Tests

```bash
python3 -m pytest -q
```

All 51 tests should pass.

---

## What Happens Next?

Each cycle processes **one** event or open loop. After running `python3 -m agents.loop`:

1. Check `python3 -m agents.loop status` to see updated priorities
2. Review `state/runs/last_run.json` for the full execution trace
3. Run `python3 -m agents.loop` again to process the next item

For continuous operation, HexClamp is typically run via an external scheduler (cron, systemd timer, or a shell loop).

---

## Common Workflow

```bash
# Setup (once)
python3 -m agents.loop init

# Enqueue work
python3 -m agents.loop enqueue "fix the login redirect"
python3 -m agents.loop enqueue "add tests for auth module"

# Run cycles (repeat)
python3 -m agents.loop
python3 -m agents.loop status

# Check logs
cat state/runs/last_run.json | jq
cat state/recent_changes.md
```
