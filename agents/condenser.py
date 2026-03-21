from __future__ import annotations

from typing import List

from models import CurrentState, Event, OpenLoop
from validate import validate_payload


def condense_state(
    events: List[Event],
    open_loops: List[OpenLoop],
    existing_state: CurrentState | None = None,
) -> CurrentState:
    state = existing_state or CurrentState(
        goal="Keep hexclamp coherent and progressing"
    )
    state.recent_events = [event.id for event in events[-10:]]
    state.active_context = [
        event.payload.get("text", "")[:160]
        for event in events[-3:]
        if event.payload.get("text")
    ]
    state.open_loops = [
        loop.id for loop in open_loops if loop.status in {"open", "blocked"}
    ]
    validate_payload(state.to_dict(), "state.schema.json")
    return state
