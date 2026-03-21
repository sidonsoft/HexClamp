# Messaging Integration Plan

## Current State

`execute_message_for_event` / `execute_message_for_loop` in `agents/executors.py`:
- Parses `text` field to detect channel (telegram/discord/signal/whatsapp/email)
- Extracts `recipient` and `content`
- Creates task artifacts: `task.json`, `brief.md`, `execution.json` in `runs/messaging_tasks/`
- Sets `status: pending_messaging_execution`
- Handles `require_approval` gate (keyword-based + policy override)
- **Delivery is not wired — nothing is ever actually sent**

The loop creates an artifact and waits. Someone (or something) must act on it manually.

---

## Goal

Wire real delivery for at least one channel, so the loop can send messages without human intervention (subject to approval gate).

---

## Channel Options

| Channel | Delivery Mechanism | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Email/SMTP** | Direct SMTP to MX | Low | Universally available, no API keys needed (just an SMTP server) |
| **Discord** | Discord webhook or bot token | Low-Medium | Webhook: no bot needed, 1 URL. Bot: more control, needs `MANAGE_MESSAGES` perms |
| **Telegram** | Bot API (`sendMessage`) | Medium | Bot token required, `require_approval` works well with this |
| **Signal** | `signal-cli` CLI | High | Local install required, number verification, not API-accessible remotely |
| **WhatsApp** | WhatsApp Business API | Very High | Phone number required, Meta API approval, complex |

**Recommendation for MVP:** Email + Discord (or Telegram). Both are accessible without special hardware (no Signal's local install requirement) and have straightforward APIs.

---

## Architecture: Delivery Layer

Introduce a `DeliveryAgent` abstraction in `agents/delivery.py`:

```python
class DeliveryAgent(ABC):
    @abstractmethod
    def send(self, recipient: str, content: str, **kwargs) -> DeliveryResult: ...

class EmailDeliveryAgent(DeliveryAgent):
    def __init__(self, smtp_host, smtp_port, username, password, from_addr):
        ...

class DiscordWebhookAgent(DeliveryAgent):
    def __init__(self, webhook_url): ...

class DiscordBotAgent(DeliveryAgent):
    def __init__(self, bot_token): ...

class TelegramBotAgent(DeliveryAgent):
    def __init__(self, bot_token): ...
```

Each agent handles:
- Connection/auth
- `recipient` format validation  
- Content encoding
- Error translation → `DeliveryResult(success, error, artifacts)`

`executors.py` calls `delivery_agent.send(recipient, content)` instead of creating dead artifacts.

---

## Approval Gate Flow

Current: `require_approval: true` in policy blocks execution, sets `status: blocked`.

Proposed: Two modes:

1. **Auto-send** (when `require_approval: false`):
   - Loop enters `open` → executor calls `delivery_agent.send()` → result written to `execution.json`

2. **Approval-required** (when `require_approval: true`):
   - Loop enters `blocked` with `blocked_by: ["approval required"]`
   - Human approves via: writing `runs/messaging_tasks/{action_id}/approved` file, or running `python3 agents/loop.py approve {action_id}`
   - Next `process_once` sees the approval file and calls `delivery_agent.send()`

---

## File Changes

| File | Change |
|------|--------|
| `agents/delivery.py` | New — `DeliveryAgent` ABC + Email/Discord/Telegram implementations |
| `agents/executors.py` | Call `delivery.send()` in `execute_message_for_loop` when not blocked; update `execution.json` with result |
| `config/delivery.yaml` | New — per-channel config (SMTP credentials, Discord webhook URLs, Telegram bot tokens) |
| `config/policies.yaml` | Add `messaging.approval_mode: "file"` or `"api"`; `messaging.channels: [discord, email]` |
| `schemas/action.schema.json` | Add `messaging_delivery` action type? Or reuse existing? |
| `tests/test_messaging_delivery.py` | New — mock delivery agents, approval flow, channel-specific tests |
| `README.md` | Update executor status: messaging 🔧 → ✅ (or keep 🔧 until at least one channel is live) |

---

## Implementation Phases

### Phase 1: Email delivery (simplest)
- `agents/delivery.py` with `EmailDeliveryAgent`
- SMTP config in `config/delivery.yaml`
- `execute_message_for_loop` calls email agent (when not blocked)
- No approval gate changes yet — keep keyword-based
- ~1 hour

### Phase 2: Discord webhook delivery
- `DiscordWebhookAgent` in `delivery.py`
- Webhook URL in `config/delivery.yaml`
- Test: send to `#alerts` channel when loop completes
- ~1 hour

### Phase 3: Approval flow (file-based)
- `approved` sentinel file in `runs/messaging_tasks/{id}/`
- `execute_message_for_loop` checks for approval before sending
- `python3 agents/loop.py approve {action_id}` helper
- ~1 hour

### Phase 4: Telegram bot delivery
- `TelegramBotAgent` in `delivery.py`
- Bot token in `config/delivery.yaml`
- Maps `recipient` (username or numeric chat ID) → `sendMessage`
- ~1-2 hours

### Phase 5: Unified config + error handling
- Consolidate all channel configs into `config/delivery.yaml`
- Per-channel error handling: retry on transient failure, fail-fast on auth error
- Update `execution.json` with delivery confirmation (message ID, timestamp)
- ~1 hour

---

## Open Questions

1. **Which channel is the primary target?** (Email? Discord? Telegram?)
2. **Who approves?** Is the approval file approach sufficient, or should there be an HTTP webhook/API?
3. **Delivery confirmation** — should the loop wait for confirmation before marking the loop resolved?
4. **Sensitive content** — should `content` be redacted from `execution.json` / logs? (e.g. OTP codes, passwords)
5. **Signal** — worth the complexity for Signal's E2E encryption guarantees?

---

## Suggested Next Step

Start with **Phase 1 (Email)** as the proof-of-concept. SMTP is universal, requires no external API accounts, and validates the delivery architecture before moving to channel-specific bots.
