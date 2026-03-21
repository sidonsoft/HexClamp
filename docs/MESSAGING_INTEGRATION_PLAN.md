# Messaging Integration Plan

## Decision

**Telegram focus.** Uses the existing OpenClaw bot (@AdellClawBot, token `8645335498:AAHYlB1Uf6qQWoZoU7o16Tm-8c2rhWUS6A0`).  
**File sentinel for approval.** `runs/messaging_tasks/{action_id}/approved` file as the gate.  
**OpenClaw channel for delivery.** OpenClaw's Telegram connection handles the actual send.

---

## Current State

`execute_message_for_event` / `execute_message_for_loop` in `agents/executors.py`:
- Parses `text` field to detect channel (telegram/discord/signal/whatsapp/email)
- Extracts `recipient` and `content`
- Creates task artifacts: `task.json`, `brief.md`, `execution.json` in `runs/messaging_tasks/`
- Sets `status: pending_messaging_execution`
- Handles `require_approval` gate (keyword-based + policy override)
- **Delivery is not wired — nothing is ever actually sent**

---

## Goal

Wire Telegram delivery using OpenClaw's existing bot, with file-sentinel approval.

---

## Architecture

### Two-part delivery

1. **Loop side** (`agents/executors.py`): parses task, creates artifacts, checks approval sentinel, calls OpenClaw tool
2. **OpenClaw side**: existing Telegram bot (`@AdellClawBot`) already connected — use it to actually send

**Integration option A — OpenClaw sessions API** (recommended):
- Loop writes the approved message to `runs/messaging_tasks/{action_id}/outbound.json`
- A separate OpenClaw cron job or subagent polls for new outbound files and calls `sessions_send` to deliver via Telegram
- OpenClaw is already authenticated and connected to Telegram — no new API credentials needed

**Integration option B — Telegram Bot API direct**:
- `agents/delivery.py` calls `https://api.telegram.org/bot{token}/sendMessage` directly via `requests`
- Needs the bot token; less elegant but more direct

Option A is preferred — leverages existing infrastructure.

### Approval sentinel flow

```
Loop creates task → blocked: approval required
                         ↓
User drops file: runs/messaging_tasks/{action_id}/approved
                         ↓
Next process_once() sees sentinel → calls OpenClaw to send via Telegram
                         ↓
execution.json updated with: {sent: true, message_id: "...", sent_at: "..."}
```

---

## File Changes

| File | Change |
|------|--------|
| `agents/delivery.py` | New — `TelegramDeliveryAgent` using OpenClaw sessions API or Bot API |
| `agents/executors.py` | Call `delivery.send()` in `execute_message_for_loop` when not blocked; update `execution.json` with result |
| `config/delivery.yaml` | Telegram channel config: bot token, default recipient |
| `config/policies.yaml` | Add `messaging.channels: [telegram]`; keep `external_send.require_approval: true` |
| `schemas/result.schema.json` | Add `sent`, `message_id` fields to messaging result |
| `tests/test_messaging_delivery.py` | New — mock delivery agent, approval sentinel flow |
| `README.md` | Update executor status: messaging 🔧 → ✅ |
| OpenClaw cron | New cron job: poll `runs/messaging_tasks/*/outbound.json`, deliver via Telegram |

---

## Implementation Phases

### Phase 1: OpenClaw integration scaffold + Telegram delivery agent
- `agents/delivery.py`: `TelegramDeliveryAgent` that writes to a queue file OpenClaw can read
- Or: `TelegramDeliveryAgent` that calls Bot API directly
- `execute_message_for_loop` calls delivery agent, skips if `require_approval` and no sentinel
- Update `execution.json` with delivery result
- ~1-2 hours

### Phase 2: Approval sentinel enforcement
- `execute_message_for_loop` checks for `runs/messaging_tasks/{action_id}/approved` sentinel
- If `require_approval` and no sentinel: loop stays `blocked`
- Sentinel file can contain optional `approved_by: @username` for audit trail
- `agents/loop.py approve {action_id}` helper to create sentinel programmatically
- ~1 hour

### Phase 3: OpenClaw cron job (Option A) or Bot API direct (Option B)
**Option A — OpenClaw sessions API:**
- Create `scripts/telegram_dispatcher.py` — polls `runs/messaging_tasks/*/outbound.json`, calls `sessions_send` to deliver
- Add OpenClaw cron job to run dispatcher every 1 minute
- Or: OpenClaw subagent triggered on new outbound file
- ~1-2 hours

**Option B — Bot API direct:**
- `requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={...})`
- Simpler architecture, no separate dispatcher needed
- ~30 min

### Phase 4: Error handling + retry
- Transient Telegram errors (rate limit, network): retry with backoff
- Auth errors (invalid token): fail fast, mark loop `failed`
- Recipient not found: mark loop `failed` with clear error
- ~1 hour

### Phase 5: Tests + docs
- Unit tests for `TelegramDeliveryAgent`
- Integration test: enqueue message → approve → verify sent
- Update README with Telegram messaging status
- ~1 hour

---

## Open Questions

1. **Option A or B?** Direct Bot API (B) is simpler. OpenClaw sessions API (A) reuses existing auth. Which does ItBurnz prefer?
2. **Default recipient:** When the message doesn't specify a recipient, who gets it? The bot admin?
3. **Message ID tracking:** Should the loop wait for Telegram's `message_id` response before marking resolved?
4. **Approval notification:** Should the bot DM the operator when a message needs approval?

---

## Suggested Next Step

Start with **Phase 1 + 2**: scaffold `TelegramDeliveryAgent` (Option B — direct Bot API), wire it into `execute_message_for_loop`, and add sentinel approval checking. This validates the full flow end-to-end without a separate dispatcher process.
