---
title: Installation
description: How to install and set up HexClamp
---

# Installation

HexClamp is a **source-only** project — there is no published PyPI package. You clone the repository and install dependencies manually.

---

## Prerequisites

| Requirement | Version / Notes |
|-------------|-----------------|
| Python | 3.11 or later |
| Git | Any recent version |
| pip | Comes with Python |
| Playwright | Only if using the `browser` executor |
| Chrome / Chromium | Only if using the `browser` executor |
| Telegram Bot Token | Only if using the `messaging` executor |

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/sidonsoft/HexClamp.git
cd HexClamp
```

---

## Step 2 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies include:

- **`pyyaml`** — Configuration file parsing (`agents.yaml`, `loops.yaml`, `policies.yaml`)
- **`jsonschema`** — JSON Schema validation for events, actions, loops, results, and state
- **`playwright`** — Browser automation (used by the `browser` executor)
- **`httpx`** — HTTP client for Telegram Bot API calls

---

## Step 3 — Install Playwright & Chromium (Browser Executor)

If you intend to use the `browser` executor, install Playwright and a headless Chromium browser:

```bash
pip install playwright
playwright install chromium
```

> **Note:** The `browser` executor is **disabled by default** in `config/agents.yaml`. Set `enabled: true` in both `config/agents.yaml` and `config/policies.yaml` to activate it.

---

## Step 4 — Configure Telegram (Messaging Executor)

The `messaging` executor lets HexClamp send and receive Telegram messages.

### 4a — Create a Telegram Bot

1. Open a chat with **@BotFather** in Telegram.
2. Send `/newbot` and follow the prompts.
3. Copy the **bot token** — it looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`.

### 4b — Authorize Operator IDs

HexClamp's approval system restricts who can approve messaging tasks. Set your Telegram user ID(s):

```bash
export TELEGRAM_AUTHORIZED_USER_IDS="123456789,987654321"
```

> To find your Telegram user ID, message **@userinfobot** or **@getidsbot**.

### 4c — Enable the Messaging Executor

In `config/agents.yaml`:

```yaml
executors:
  messaging:
    enabled: true   # was false
    model: default
    role: draft_or_send_with_approval
```

In `config/policies.yaml`:

```yaml
executors:
  messaging:
    enabled: true   # was false
```

### 4d — Set the Bot Token

```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
```

> **Security:** Never commit production tokens to version control. Consider using a `.env` file loaded by your shell profile, or a secrets manager.

---

## Step 5 — Bootstrap Runtime State

```bash
python3 -m agents.loop init
```

This creates the `state/` directory structure:

```
state/
  current_state.json    # The condensed system state
  event_queue.json      # Pending events awaiting processing
  open_loops.json       # Active tasks and their status
  polling_state.json    # Telegram polling offset tracker
  circuit_breaker.json  # Circuit breaker status
  recent_changes.md     # Log of all actions taken
  runs/                 # Individual run logs
    last_run.json
    run-20260101T120000Z.json
```

---

## Step 6 — Verify the Installation

```bash
python3 -m agents.loop status
```

You should see:

```
=== HexClamp Status ===
Goal: Keep hexclamp coherent and progressing

Queue Size: 0 events
Open Loops: 0
...
```

---

## Running the Tests

HexClamp ships with 51 tests:

```bash
python3 -m pytest -q
```

All tests should pass on a clean install.

---

## CI

Every push to `main` and every pull request runs:

- `ruff check`
- `ruff format --check`
- `mypy agents/ scripts/ --ignore-missing-imports`
- `pytest --cov`

---

## Next Steps

- Read the [Quick Start](quickstart.md) guide to run your first cycle.
- Review the [Configuration](configuration.md) reference for fine-tuning.
- Explore the [Architecture](architecture.md) overview to understand how it all fits together.
