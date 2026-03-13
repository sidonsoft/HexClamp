from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from models import Event
from validate import validate_payload


def observe_chat_message(text: str, priority: str = "normal") -> Event:
    event = Event(
        id=f"evt-{uuid4()}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="chat",
        kind="request",
        payload={"text": text},
        tags=["user"],
        priority=priority,
    )
    validate_payload(event.to_dict(), "event.schema.json")
    return event
