"""Research executor - handles research task execution."""

from __future__ import annotations

from datetime import datetime, timezone

from agents.models import Action, Event, OpenLoop
from agents.executors.base import (
    STALE_EVIDENCE_THRESHOLD,
    _initial_loop_state,
    _write_change,
)


def execute_research_for_event(
    action: Action, event: Event
) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute research task for an event."""
    loop_status, next_step, blocked_by, summary = _initial_loop_state(event, "research")
    artifact = _write_change(action, summary)
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=event.payload.get("text", "")[:80] or f"Follow up event {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="research",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=[event.id],
    )
    return summary, [event.id], [artifact], loop


def execute_research_for_loop(
    action: Action, loop: OpenLoop
) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute research task for a loop."""
    now = datetime.now(timezone.utc).isoformat()

    if loop.status == "blocked":
        summary = f"Loop '{loop.title}' remains blocked pending dependency resolution."
        loop.next_step = "Await unblock signal before further execution"
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "stale"
            loop.next_step = "Stale blocked loop; requires operator review"
            summary = (
                f"Loop '{loop.title}' became stale after repeated blocked reviews."
            )
    else:
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "resolved"
            loop.next_step = (
                "Research loop exhausted; treat as resolved unless reopened"
            )
            summary = f"Loop '{loop.title}' reached resolution threshold."
        else:
            loop.status = "open"
            loop.next_step = f"Escalate or specialize execution for: {loop.title}"
            summary = f"Reviewed research loop '{loop.title}' and refreshed next step."

    loop.updated_at = now
    loop.evidence.append(action.id)
    artifact = _write_change(action, summary)
    return summary, loop.evidence, [artifact], loop
