# HexClamp

**v1.0** — An inspectable autonomous agent loop scaffold.

HexClamp separates observation, condensation, planning, execution, verification, and persistence into distinct, auditable stages. File-backed state means every decision, every action, and every result survives restarts and is inspectable at any time.

## Core loop

```
Observe → Condense → Plan → Execute → Verify → Persist
```

Each cycle loads current state, generates actions from ranked open loops, executes one action, verifies the result, and persists the updated state. Everything is file-backed — no invisible prompt state.

## Design principles

1. Raw inputs get normalized before use.
2. Condensed state is the default context, not the whole world.
3. Executors have narrow authority and clear contracts.
4. Verification is mandatory for meaningful actions.
5. File-backed state beats invisible prompt state.
6. Persistent briefs and open loops prevent rediscovery.

## Architecture

```
agents/
  loop.py       # Main cycle: load → condense → plan → execute → verify → persist
  models.py     # Dataclasses: Event, Action, OpenLoop, Result, CurrentState
  observer.py   # Normalize raw inputs into Events
  condenser.py  # Compress events + loops into CurrentState
  planner.py    # Rank open loops, classify inputs, select next actions
  verifier.py   # Validate claimed results against evidence
  executors/
    __init__.py      # Public executor exports (backward-compatible surface)
    base.py          # Shared executor helpers, policies, quality gates
    browser.py       # Browser executor
    code_executor.py # Code executor
    messaging.py     # Messaging executor
    research.py      # Research executor
  store.py      # Atomic JSON file I/O
  validate.py   # JSON Schema validation with caching

config/
  policies.yaml   # Verification gates, loop control, executor config
  agents.yaml     # Model routing per agent
  loops.yaml      # Loop priority and ownership

schemas/
  event.schema.json
  action.schema.json
  loop.schema.json
  result.schema.json
  state.schema.json

prompts/
  observer.md       # Role prompt for the observer
  condenser.md      # Role prompt for the condenser
  planner.md        # Role prompt for the planner
  verifier.md       # Role prompt for the verifier
  executors/
    research.md    # Role prompt for the research executor
    code.md        # Role prompt for the code executor
    browser.md     # Role prompt for the browser executor
    messaging.md   # Role prompt for the messaging executor
```

## Executors

| Executor  | Status | Notes |
|-----------|--------|-------|
| research  | ✅ Active | Grounded summaries → `state/recent_changes.md` |
| code      | ✅ Active | Coding agent briefs → runs in target workspace |
| browser   | ✅ Active | Playwright headless Chromium — navigates, screenshots, extracts text |
| messaging | ✅ Active | Telegram Bot API — auto-send or sentinel-approved; handles 403/400/429 |
| system    | ❌ Removed | No executor branch — reduces attack surface |

## Quick start

```bash
# Bootstrap runtime state
python3 agents/loop.py init

# Enqueue tasks
python3 agents/loop.py enqueue "investigate the auth bug"
python3 agents/loop.py enqueue "review PR #42"

# Run one cycle
python3 agents/loop.py

# Run tests
make test
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes (for messaging) | none | Bot token for Telegram delivery. Required when the messaging executor is enabled. Do not commit production tokens. |

## Testing

49 tests — all passing:

```bash
python3 -m pytest -q
```

| Test file | What it covers |
|-----------|---------------|
| `test_bootstrap.py` | Runtime bootstrap |
| `test_browser_executor.py` | Navigation, URL validation, error handling |
| `test_integration.py` | End-to-end enqueue → plan → execute → verify |
| `test_message_parser.py` | Message normalization |
| `test_messaging_delivery.py` | TelegramDeliveryAgent result handling |
| `test_planner.py` | Loop ranking and urgency scoring |
| `test_task_completion.py` | Task artifact verification |

## CI

GitHub Actions runs `ruff check`, `ruff format --check`, `mypy agents/ scripts/ --ignore-missing-imports`, and `pytest --cov` on every push to `main` and on all pull requests.

## Adding a new executor

1. Add the executor implementation to the appropriate module under `agents/executors/` and re-export it from `agents/executors/__init__.py`
2. Add the action type to `schemas/action.schema.json` enum
3. Update `agents/planner.py` routing so the new executor can be selected
4. Create a role prompt in `prompts/executors/<name>.md`
5. Add `verification.required_for` entry in `config/policies.yaml` if evidence is needed
6. Add tests in `tests/`
7. Update this README's executor status table
