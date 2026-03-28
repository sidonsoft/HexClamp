"""Telegram polling and authorization for HexClamp agent loop.

Handles Telegram message polling and user authorization.
"""

from typing import Dict, Any, List, Optional

from agents.store import read_json, write_json, STATE_DIR
from agents.delivery import TelegramDeliveryAgent

# File paths
POLLING_STATE_PATH = STATE_DIR / "polling.json"
AUTHORIZED_USERS_PATH = STATE_DIR / "authorized_users.json"


def _is_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    authorized = read_json(AUTHORIZED_USERS_PATH, default={})
    return str(user_id) in authorized or user_id in authorized


def _authorize(user_id: int, username: Optional[str] = None) -> None:
    """Authorize a user."""
    authorized = read_json(AUTHORIZED_USERS_PATH, default={})
    authorized[str(user_id)] = {"username": username, "user_id": user_id}
    write_json(AUTHORIZED_USERS_PATH, authorized)


def poll_events() -> Dict[str, Any]:
    """Poll Telegram for new messages and enqueue them as events.
    
    Returns:
        Dict with keys: events (list), ignored (int), approvals (int)
    """
    from agents.loop.state_loaders import append_to_event_queue
    from agents.observer import observe_chat_message
    
    # Load offset
    state = read_json(POLLING_STATE_PATH, default={"last_offset": None})
    offset = state.get("last_offset")

    agent = TelegramDeliveryAgent()
    updates = agent.get_updates(offset=offset)

    events = []
    ignored = 0
    approvals = 0
    max_update_id = int(offset) if offset else 0

    for update in updates:
        raw_id = update.get("update_id")
        if not isinstance(raw_id, int):
            ignored += 1
            continue
        update_id: int = raw_id
        if max_update_id and update_id >= max_update_id:
            max_update_id = update_id + 1

        message = update.get("message")
        if not message:
            ignored += 1
            continue

        user = message.get("from", {})
        user_id = user.get("id")
        username = user.get("username")

        if not user_id:
            ignored += 1
            continue

        text = message.get("text", "")
        if not text:
            ignored += 1
            continue

        # Authorization check
        if not _is_authorized(user_id):
            if text.strip().lower() == "authorize":
                _authorize(user_id, username)
                approvals += 1
                # Send confirmation
                agent.send_message(
                    chat_id=user_id,
                    text="✅ Authorized! You can now use the bot.",
                )
            ignored += 1
            continue

        # Enqueue event
        event = observe_chat_message(text, metadata={
            "user_id": user_id,
            "username": username,
            "message_id": message.get("message_id"),
        })
        append_to_event_queue(event)
        events.append(event)

    # Save offset
    if max_update_id:
        write_json(POLLING_STATE_PATH, {"last_offset": str(max_update_id)})

    return {
        "events": events,
        "ignored": ignored,
        "approvals": approvals,
    }
