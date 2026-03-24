---
title: Configuration
description: Configuration reference for HexClamp
---

# Configuration

HexClamp is configured through three YAML files in `config/` and a set of environment variables.

---

## `config/agents.yaml` — Model Routing & Executor Toggle

Controls which executors are active and which LLM model each agent stage uses.

```yaml
observer:
  enabled: true
  model: default
  role: normalize_inputs

condenser:
  enabled: true
  model: default
  role: compress_context

planner:
  enabled: true
  model: default
  role: choose_next_actions

verifier:
  enabled: true
  model: default
  role: validate_claimed_results

executors:
  research:
    enabled: true
    model: default
    role: gather_and_summarize
  code:
    enabled: false          # Disabled by default
    model: default
    role: modify_and_test
  browser:
    enabled: false          # Disabled by default
    model: default
    role: navigate_and_extract
  messaging:
    enabled: false          # Disabled by default; enable when bot is ready
    model: default
    role: draft_or_send_with_approval
```

### Key Points

- **`model: default`** — Uses whatever model your LLM client is configured to use by default. You can replace this with a specific model name (e.g., `gpt-4o`, `claude-3-5-sonnet`) if your client supports model selection.
- **Executors default to `false`** — `research` is the only executor enabled out of the box. Enable `code`, `browser`, and `messaging` only after you've set up their dependencies.
- The `system` executor is not supported and has been removed.

---

## `config/loops.yaml` — Loop Priority & Scheduling

Controls three loop tiers with different cadence and focus:

```yaml
fast_loop:
  enabled: true
  trigger: event_or_poll
  interval_seconds: 300
  tasks:
    - observe_new_events
    - refresh_open_loops
    - inspect_recent_failures

medium_loop:
  enabled: true
  trigger: schedule
  interval_seconds: 3600
  tasks:
    - rebuild_condensed_state_if_changed
    - reprioritize_actions
    - prune_stale_items

slow_loop:
  enabled: true
  trigger: schedule
  interval_seconds: 86400
  tasks:
    - summarize_progress
    - extract_durable_memory
    - prune_junk_state
    - generate_operator_digest
```

### Loop Tiers

| Tier | Cadence | Purpose |
|------|---------|---------|
| **fast** | Every 5 min | React to new events and failures |
| **medium** | Every 1 hr | Reprioritize and clean up |
| **slow** | Daily | Long-term memory and digest |

---

## `config/policies.yaml` — Verification Gates & Loop Control

Enforces quality gates, approval requirements, and retry policies.

```yaml
external_send:
  require_approval: true

config_mutation:
  require_backup: true
  require_validation: true

retries:
  max_attempts: 3
  require_backoff: true

verification:
  required_for:
    - code
    - browser
    - messaging

executors:
  research:
    enabled: true
  code:
    enabled: true
  browser:
    enabled: true
  messaging:
    enabled: true

loop_control:
  allow_self_requeue_forever: false
  require_evidence: true

cost_control:
  prefer_condensed_state: true
  prefer_low_cost_observation: true
```

### Key Policies

| Policy | Default | Effect |
|--------|---------|--------|
| `verification.required_for` | `code`, `browser`, `messaging` | These executors must supply evidence before being marked verified |
| `external_send.require_approval` | `true` | Messaging tasks require operator approval before sending |
| `retries.max_attempts` | `3` | Maximum retry attempts before a task is marked failed |
| `loop_control.allow_self_requeue_forever` | `false` | Prevents infinite self-requeue loops |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | For messaging | none | Telegram bot token from @BotFather |
| `TELEGRAM_AUTHORIZED_USER_IDS` | For polling/approvals | none | Comma-separated Telegram user IDs authorized to approve tasks |

> See the [Environment Variables](environment.md) reference for the full list.

---

## Configuration Precedence

The loop engine reads executor enabled status from **both** `config/agents.yaml` and `config/policies.yaml`. An executor is considered enabled only if **both** files agree. This prevents accidental activation from a single config change.

---

## Best Practices

- **Never commit production tokens** to `agents.yaml` or the environment.
- Use a `.env` file or your shell profile to manage `TELEGRAM_BOT_TOKEN` and `TELEGRAM_AUTHORIZED_USER_IDS`.
- Review `config/policies.yaml` before enabling `code` or `browser` executors in a shared environment — verification is there for a reason.
- Keep `model: default` in `agents.yaml` unless you specifically need to route a stage to a different model.
