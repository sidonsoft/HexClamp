---
title: Environment Variables
description: HexClamp environment variables reference
---

# Environment Variables

HexClamp uses a small set of environment variables for Telegram integration and LLM API keys. All others are configured via YAML files in `config/`.

---

## Telegram Variables

### `TELEGRAM_BOT_TOKEN`

| Property | Value |
|----------|-------|
| Required | Only if using the `messaging` executor |
| Default | None |

The bot token issued by **@BotFather** when you created your Telegram bot. Used by `TelegramDeliveryAgent` to send and poll messages.

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
```

> **Security:** Never commit this token to version control. Use a `.env` file or your shell profile.

---

### `TELEGRAM_AUTHORIZED_USER_IDS`

| Property | Value |
|----------|-------|
| Required | For polling and approval workflows |
| Default | None |

Comma-separated list of Telegram user IDs authorised to approve messaging tasks. Any user whose ID is not in this list will receive an `Unauthorized approval attempt` response if they try to approve a task.

```bash
export TELEGRAM_AUTHORIZED_USER_IDS="123456789,987654321"
```

> To find your Telegram user ID, send any message to **@userinfobot** or **@getidsbot**.

---

## LLM API Keys

HexClamp delegates LLM calls to your configured LLM client. The client library (e.g., OpenAI Python SDK, Anthropic SDK) reads its own standard environment variables:

### `OPENAI_API_KEY`

| Property | Value |
|----------|-------|
| Required | Only if using OpenAI models |
| Default | None (uses SDK default or configured client) |

```bash
export OPENAI_API_KEY="sk-..."
```

Used by the LLM client when the model in `config/agents.yaml` is set to an OpenAI model.

---

### `ANTHROPIC_API_KEY`

| Property | Value |
|----------|-------|
| Required | Only if using Anthropic/Claude models |
| Default | None |

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Optional / Advanced Variables

### `HEXCLAMP_BASE_PATH`

| Property | Value |
|----------|-------|
| Required | No |
| Default | Repository root |

Override the base directory for the HexClamp workspace (where `config/`, `state/`, `schemas/`, etc. are located). Mostly useful for testing.

---

## Setting Variables

### Option 1 — Shell profile (.zshrc, .bashrc)

```bash
# ~/.zshrc
export TELEGRAM_BOT_TOKEN="your-token-here"
export TELEGRAM_AUTHORIZED_USER_IDS="123456789"
export OPENAI_API_KEY="sk-..."
```

### Option 2 — .env file

Create a `.env` file in the HexClamp repository root (and add it to `.gitignore`):

```
TELEGRAM_BOT_TOKEN=your-token-here
TELEGRAM_AUTHORIZED_USER_IDS=123456789
OPENAI_API_KEY=sk-...
```

Load it before running HexClamp:

```bash
set -a && source .env && set +a
python3 -m agents.loop status
```

### Option 3 — Inline

```bash
TELEGRAM_BOT_TOKEN="your-token-here" python3 -m agents.loop poll
```

---

## Security Notes

- **Never commit API keys or bot tokens to Git.**
- Add `.env` to `.gitignore` before running HexClamp in a git repository.
- `TELEGRAM_AUTHORIZED_USER_IDS` is the only Telegram authorisation mechanism — there is no other authentication layer for the polling/approval workflow.
- The `system` executor is removed; there is no backdoor execution path.
