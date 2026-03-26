from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from agents.models import CurrentState, Event, OpenLoop
from agents.store import STATE_DIR, write_json
from agents.validate import validate_payload


CONDENSATION_TRIGGERS = {
    "context_tokens": 0.5,  # Condense at 50% context window
    "loop_count": 10,       # Condense after 10 loops
    "event_count": 20,      # Condense after 20 events
    "error_detected": True, # Force condense on errors
}


def should_condense(
    events: List[Event],
    open_loops: List[OpenLoop],
    consecutive_errors: int = 0,
) -> bool:
    """
    Check if condensation should be triggered based on configured thresholds.
    
    Returns True if any trigger condition is met.
    """
    # Check event count threshold
    if len(events) >= CONDENSATION_TRIGGERS["event_count"]:
        return True
    
    # Check error threshold
    if consecutive_errors > 0 and CONDENSATION_TRIGGERS["error_detected"]:
        return True
    
    # Note: context_tokens and loop_count require additional state tracking
    # For now, we trigger on event_count and errors
    return False


def create_handoff(
    completed_loops: List[OpenLoop],
    current_state: CurrentState,
    next_actions: List[str],
    open_questions: Optional[List[str]] = None,
    gotchas: Optional[List[str]] = None,
) -> Dict:
    """
    Create a handoff file for explicit context reset.
    
    This captures the current state when condensing, allowing the next
    cycle to resume with full context without loading the entire history.
    """
    handoff = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_loops": [
            {
                "id": loop.id,
                "title": loop.title,
                "completed_at": loop.updated_at,
            }
            for loop in completed_loops
        ],
        "current_state": {
            "goal": current_state.goal,
            "active_context": current_state.active_context,
            "open_loops": current_state.open_loops,
        },
        "next_actions": next_actions,
        "open_questions": open_questions or [],
        "gotchas": gotchas or [],
    }
    return handoff


def condense_with_handoff(
    events: List[Event],
    open_loops: List[OpenLoop],
    existing_state: CurrentState | None = None,
    consecutive_errors: int = 0,
) -> tuple[CurrentState, Optional[Dict]]:
    """
    Condense state and create handoff file if triggers are met.
    
    Returns:
        tuple: (condensed_state, handoff_dict or None)
    """
    # Check if condensation should be triggered
    trigger_condensation = should_condense(events, open_loops, consecutive_errors)
    
    # Perform standard condensation
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
    
    # Identify completed loops for handoff
    completed_loops = [
        loop for loop in open_loops 
        if loop.status in {"resolved", "completed"}
    ]
    
    # Create handoff if triggered
    handoff = None
    if trigger_condensation and completed_loops:
        handoff = create_handoff(
            completed_loops=completed_loops,
            current_state=state,
            next_actions=state.current_actions,
            open_questions=[],  # Could be populated from loop analysis
            gotchas=[
                f"Condensed {len(events)} events to {len(state.recent_events)} recent",
                f"{len(completed_loops)} loops completed in this session",
            ] if completed_loops else [],
        )
        # Write handoff to disk
        handoff_path = STATE_DIR / "handoff.json"
        write_json(handoff_path, handoff)
    
    validate_payload(state.to_dict(), "state.schema.json")
    return state, handoff


def condense_state(
    events: List[Event],
    open_loops: List[OpenLoop],
    existing_state: CurrentState | None = None,
) -> CurrentState:
    """
    Legacy condense_state function for backward compatibility.
    
    Wraps condense_with_handoff but discards the handoff.
    """
    state, _ = condense_with_handoff(events, open_loops, existing_state)
    return state


def load_handoff() -> Optional[Dict]:
    """
    Load handoff file if it exists.
    
    Returns the handoff dict or None if no handoff exists.
    """
    handoff_path = STATE_DIR / "handoff.json"
    if handoff_path.exists():
        try:
            with open(handoff_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def clear_handoff() -> None:
    """
    Remove handoff file after it has been consumed.
    """
    handoff_path = STATE_DIR / "handoff.json"
    if handoff_path.exists():
        handoff_path.unlink()
