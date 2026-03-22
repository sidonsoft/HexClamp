from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from agents.models import Event
from agents.validate import validate_payload


def observe_chat_message(
    text: str, priority: str = "normal", metadata: dict | None = None
) -> Event:
    payload = {"text": text}
    if metadata:
        payload.update(metadata)

    event = Event(
        id=f"evt-{uuid4()}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="chat",
        kind="request",
        payload=payload,
        tags=["user"],
        priority=priority,
    )
    validate_payload(event.to_dict(), "event.schema.json")
    return event
