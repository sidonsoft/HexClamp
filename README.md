# hydra-claw-loop

A practical scaffold for an inspectable autonomous agent loop.

## Goal

Build a system that stays coherent over time by separating:
- **observation** — normalize raw inputs into events
- **condensation** — compress events + state into working context
- **planning** — rank open loops and select next actions
- **execution** — run tasks through specialized executors
- **verification** — validate claimed results before accepting them
- **persistence** — file-backed state that survives restarts

## Core loop

```
Observe → Condense → Plan → Execute → Verify → Persist
```

Each cycle loads current state, generates actions from ranked open loops, executes one action, verifies the result, and persists the updated state. The loop is fully file-backed — no invisible prompt state.

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
  executors.py  # Task executors: research, code, browser, messaging
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
  observer.md     # Role prompt for the observer
  condenser.md    # Role prompt for the condenser
  planner.md      # Role prompt for the planner
  verifier.md     # Role prompt for the verifier
  executors/      # Per-executor role prompts
```

## Executor status

| Executor   | Status | Notes |
|------------|--------|-------|
| research   | ✅ Active | Grounded summaries → `state/recent_changes.md` |
| code       | ✅ Active | Coding agent tasks → runs in target workspace |
| browser    | ✅ Active | Playwright headless Chromium — navigates, screenshots, extracts text |
| messaging  | ✅ Active | Telegram Bot API — auto-send or sentinel-approved; handles 403/400/429 |
| system     | ⚠️ Removed | Removed — no executor branch, reduces attack surface |

## Code review findings — all resolved

All 11 findings from the Codex architecture review are fixed and merged:

| # | Finding | Status |
|---|---------|--------|
| #6 | Planner/executor urgency index mismatch | ✅ Fixed |
| #7 | Code executor ran in scratch dir, not workspace | ✅ Fixed |
| #8 | Events lost on executor/verification failure | ✅ Fixed |
| #9 | Non-atomic JSON writes (fcntl deadlock) | ✅ Fixed |
| #10 | Pending task files counted as completion evidence | ✅ Fixed |
| #11 | Prompt injection risk (untrusted chat → coding agents) | ⚠️ Opt-in gate |
| #12 | System action classified with no executor branch | ✅ Fixed (removed) |
| #13 | Policy flags and approval not enforced | ✅ Fixed |
| #14 | Invalid datetimes silently fell back to "now" | ✅ Fixed |
| #15 | Schema registry rebuilt from disk on every call | ✅ Fixed |
| #16 | Browser URL only encoded spaces | ✅ Fixed (full URL validation: schemes, IPv4/IPv6 private ranges, octet range checks) |
| #17 | Messaging executor created artifacts but never delivered | ✅ Fixed (Telegram Bot API direct, sentinel approval) |

**Issue #11 note:** Prompt injection risk is mitigated by an opt-in `require_approval` gate in `config/policies.yaml`. Set `policies.code.require_approval: true` to block autonomous code execution when untrusted chat input can reach the loop. The approval gate blocks the external agent from spawning until a human explicitly approves.

## Testing

```bash
make test
# or
python3 -m unittest discover -s tests -v
```

**Automated test coverage:**
- `test_message_parser.py` — message normalization regression tests
- `test_planner.py` — loop ranking and urgency scoring tests
- `test_task_completion.py` — task artifact verification tests
- `test_bootstrap.py` — runtime bootstrap tests
- `test_integration.py` — end-to-end enqueue → plan → task artifact integration test

## CI

GitHub Actions runs syntax checks and the full test suite on every push to `main` and on all pull requests.

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    - python setup + requirements
    - syntax check: python -m py_compile on all .py files
    - pytest tests/ -v --tb=short
  lint:
    - ruff check .
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes (prod) | dev fallback | Bot token for Telegram delivery. Set before running in production. |

> **Security note:** Do not commit production tokens to source control. Use environment variables or a secrets manager.

## Runtime bootstrap

Runtime state (`state/current_state.json`, `state/event_queue.json`, `state/open_loops.json`) is created automatically on first run.

Manual bootstrap:

```bash
python3 agents/loop.py init
# or
python3 scripts/bootstrap_runtime.py
```

Generated runtime files (`runs/`, `state/current_state.json`, `state/event_queue.json`, `state/open_loops.json`, `state/recent_changes.md`) are excluded from source control — see `.gitignore`.

## Running the loop

```bash
# Initialize / enqueue a task
python3 agents/loop.py enqueue "investigate the auth bug"
python3 agents/loop.py enqueue "review PR #42"

# Run one cycle
python3 agents/loop.py

# Interactive repl
python3 agents/loop.py repl
```

## Adding a new executor

1. Add the executor function to `agents/executors.py` (e.g., `execute_<name>_for_loop`)
2. Add the action type to `schemas/action.schema.json` enum
3. Add a role prompt in `prompts/executors/<name>.md`
4. Add `verification.required_for` entry in `config/policies.yaml` if the executor requires evidence
5. Add tests in `tests/`
6. Update this README's executor status table
