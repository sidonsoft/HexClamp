---
title: HexClamp — Home
description: An inspectable autonomous agent loop scaffold
---

# HexClamp

**An inspectable autonomous agent loop scaffold.**

HexClamp separates observation, condensation, planning, execution, verification, and persistence into distinct, auditable stages. File-backed state means every decision, every action, and every result survives restarts and is inspectable at any time.

---

## The Core Loop

```
Observe → Condense → Plan → Execute → Verify → Persist
```

| Stage | What it does |
|-------|-------------|
| **Observe** | Raw inputs (messages, events, poll results) are normalized into structured `Event` objects |
| **Condense** | Events and open loops are compressed into a focused `CurrentState` — the context for the next decision |
| **Plan** | Open loops are ranked by urgency; the most important action is selected |
| **Execute** | The chosen action runs through a specialist executor (research, code, browser, messaging) |
| **Verify** | The claimed result is checked against evidence before being accepted |
| **Persist** | Verified state is written to disk — JSON files in `state/` — so nothing is ever lost |

Each cycle loads current state, generates actions from ranked open loops, executes one action, verifies the result, and persists the updated state. **Everything is file-backed** — no invisible prompt state.

---

## Why HexClamp?

- **Inspectable by design** — Every event, action, and result lives in plain JSON. You can read the state of the system at any time.
- **Multi-executor architecture** — Specialist executors for research, code execution, browser automation (Playwright), and Telegram messaging.
- **Mandatory verification** — Meaningful actions (code, browser, messaging) must provide evidence before being marked verified.
- **Circuit breaker** — Three consecutive errors trip the breaker and halt the loop to prevent runaway behaviour.
- **Telegram-native** — Poll inbound messages, enqueue events, and handle operator approvals without manual CLI overhead.
- **File-backed persistence** — State survives process restarts. No invisible context.

---

## Key Design Principles

1. **Raw inputs are normalized before use.**
2. **Condensed state is the default context**, not the whole world.
3. **Executors have narrow authority and clear contracts.**
4. **Verification is mandatory for meaningful actions.**
5. **File-backed state beats invisible prompt state.**
6. **Persistent briefs and open loops prevent rediscovery.**

---

## Executor Status

| Executor | Status | Notes |
|----------|--------|-------|
| `research` | ✅ Active | Grounded summaries → `state/recent_changes.md` |
| `code` | ✅ Active | Coding agent briefs → runs in target workspace |
| `browser` | ✅ Active | Playwright headless Chromium — navigates, screenshots, extracts text |
| `messaging` | ✅ Active | Telegram Bot API — auto-send or sentinel-approved |
| `system` | ❌ Removed | No executor branch — reduces attack surface |

---

## Quick Start

```bash
# Bootstrap runtime state
python3 -m agents.loop init

# Enqueue tasks
python3 -m agents.loop enqueue "investigate the auth bug"

# Run one cycle
python3 -m agents.loop

# Check system status
python3 -m agents.loop status

# Poll Telegram for inbound messages
python3 -m agents.loop poll
```

See [Quick Start](quickstart.md) for the full guide.

---

## Resources

- [GitHub Repository](https://github.com/sidonsoft/HexClamp)
- [Installation Guide](installation.md)
- [Architecture Overview](architecture.md)
- [The O→C→P→E→V→P Loop](loop.md)
- [Executors Reference](executors.md)
