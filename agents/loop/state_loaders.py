"""State loading and saving for HexClamp agent loop.

Handles persistence of current state, event queue, and loop history.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.store import (
    STATE_DIR,
    RUNS_DIR,
    read_json,
    write_json,
    append_json_array,
)
from agents.models import CurrentState, Event, OpenLoop

# File paths
CURRENT_STATE_PATH = STATE_DIR / "current_state.json"
EVENT_QUEUE_PATH = STATE_DIR / "event_queue.json"
LOOPS_PATH = STATE_DIR / "loops.json"
OPEN_LOOPS_PATH = STATE_DIR / "open_loops.json"  # Backward compatibility alias
CIRCUIT_BREAKER_PATH = STATE_DIR / "circuit_breaker.json"  # Backward compatibility
POLLING_STATE_PATH = STATE_DIR / "polling.json"  # For telegram_poll
AUTHORIZED_USERS_PATH = STATE_DIR / "authorized_users.json"  # For telegram_poll


def load_current_state() -> Optional[CurrentState]:
    """Load current state from disk."""
    state_dict = read_json(CURRENT_STATE_PATH, default=None)
    if state_dict is None:
        return None
    return CurrentState.from_dict(state_dict)


def save_current_state(state: CurrentState) -> None:
    """Save current state to disk."""
    write_json(CURRENT_STATE_PATH, state.to_dict())


def load_event_queue() -> List[Event]:
    """Load event queue from disk."""
    events_list = read_json(EVENT_QUEUE_PATH, default=[])
    return [Event.from_dict(e) for e in events_list]


def save_event_queue(events: List[Event]) -> None:
    """Save event queue to disk (overwrite)."""
    write_json(EVENT_QUEUE_PATH, [e.to_dict() for e in events])


def append_to_event_queue(event: Event) -> None:
    """Append single event to queue."""
    append_json_array(EVENT_QUEUE_PATH, event.to_dict())


def load_loops() -> List[OpenLoop]:
    """Load open loops from disk."""
    loops_list = read_json(LOOPS_PATH, default=[])
    return [OpenLoop.from_dict(l) for l in loops_list]


def save_loops(loops: List[OpenLoop]) -> None:
    """Save loops to disk (overwrite)."""
    write_json(LOOPS_PATH, [l.to_dict() for l in loops])


def append_to_loops(loop: OpenLoop) -> None:
    """Append single loop to history."""
    append_json_array(LOOPS_PATH, loop.to_dict())


def replace_or_append_loop(loop: OpenLoop) -> None:
    """Replace existing loop with same ID, or append if new."""
    loops = load_loops()
    replaced = False
    for i, existing in enumerate(loops):
        if existing.id == loop.id:
            loops[i] = loop
            replaced = True
            break
    if not replaced:
        loops.append(loop)
    save_loops(loops)
