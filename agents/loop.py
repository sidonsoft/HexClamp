"""HexClamp agent loop - backward compatibility wrapper.

This module now re-exports from the decomposed agents.loop package.
Original monolithic implementation split into:
    - circuit_breaker.py
    - config_loader.py
    - state_loaders.py
    - telegram_poll.py
    - status_display.py
    - loop_ops.py
    - executor_dispatch.py
    - core.py

For new code, import directly from agents.loop:
    from agents.loop import process_once, poll_events, ...
"""

# Re-export all public API from decomposed package
from agents.loop import (
    process_once,
    poll_events,
    print_status,
    queue_event,
    is_circuit_open,
    get_circuit_state,
    MAX_CONSECUTIVE_ERRORS,
    load_config,
    executor_enabled,
    get_executor_config,
    load_current_state,
    save_current_state,
    load_event_queue,
    save_event_queue,
    append_to_event_queue,
    load_loops,
    save_loops,
    append_to_loops,
    replace_or_append_loop,
    is_stale,
    prune_old_loops,
    get_active_loops,
    create_loop,
    EVENT_QUEUE_PATH,
    LOOPS_PATH,
    CURRENT_STATE_PATH,
    CIRCUIT_STATE_PATH,
    POLLING_STATE_PATH,
    OPEN_LOOPS_PATH,
    CIRCUIT_BREAKER_PATH,
    AUTHORIZED_USERS_PATH,
)

# Backward compatibility: re-export circuit breaker state variables
from agents.loop.circuit_breaker import (
    _circuit_open,
    _consecutive_errors,
)

# Backward compatibility: re-export from store
from agents.store import bootstrap_runtime_state, STATE_DIR, RUNS_DIR

# For backward compatibility, also expose queue_event from state_loaders
def queue_event(text: str, priority: str = "normal", metadata: dict | None = None):
    """Queue a chat message as an event."""
    from agents.observer import observe_chat_message
    from agents.loop.state_loaders import append_to_event_queue
    event = observe_chat_message(text, priority=priority, metadata=metadata)
    append_to_event_queue(event)
    return event

__all__ = [
    "process_once",
    "poll_events",
    "print_status",
    "queue_event",
    "is_circuit_open",
    "get_circuit_state",
    "MAX_CONSECUTIVE_ERRORS",
    "load_config",
    "executor_enabled",
    "get_executor_config",
    "load_current_state",
    "save_current_state",
    "load_event_queue",
    "save_event_queue",
    "append_to_event_queue",
    "load_loops",
    "save_loops",
    "append_to_loops",
    "replace_or_append_loop",
    "is_stale",
    "prune_old_loops",
    "get_active_loops",
    "create_loop",
    "EVENT_QUEUE_PATH",
    "LOOPS_PATH",
    "CURRENT_STATE_PATH",
    "CIRCUIT_STATE_PATH",
    "POLLING_STATE_PATH",
    "OPEN_LOOPS_PATH",
    "CIRCUIT_BREAKER_PATH",
    "AUTHORIZED_USERS_PATH",
    # Backward compatibility
    "_circuit_open",
    "_consecutive_errors",
    "bootstrap_runtime_state",
    "STATE_DIR",
    "RUNS_DIR",
]
