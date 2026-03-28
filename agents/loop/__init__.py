"""HexClamp agent loop package.

Decomposed from monolithic loop.py (544 lines) into modular components.

Modules:
    - circuit_breaker: Failure prevention with circuit breaker pattern
    - config_loader: YAML configuration loading
    - state_loaders: State persistence (events, loops, current state)
    - telegram_poll: Telegram message polling and authorization
    - status_display: Console status output
    - loop_ops: Loop lifecycle (create, prune, staleness)
    - executor_dispatch: Route actions to executors
    - core: Main process_once() loop

Usage:
    from agents.loop import process_once
    result = process_once()
"""

from agents.loop.circuit_breaker import (
    is_circuit_open,
    get_circuit_state,
    MAX_CONSECUTIVE_ERRORS,
    _circuit_open,
    _consecutive_errors,
    _reset_circuit,
    _reset_circuit_breaker,
)
from agents.loop.config_loader import (
    load_config,
    executor_enabled,
    get_executor_config,
)
from agents.loop.state_loaders import (
    load_current_state,
    save_current_state,
    load_event_queue,
    save_event_queue,
    append_to_event_queue,
    load_loops,
    save_loops,
    append_to_loops,
    replace_or_append_loop,
    EVENT_QUEUE_PATH,
    LOOPS_PATH,
    CURRENT_STATE_PATH,
    OPEN_LOOPS_PATH,
    CIRCUIT_BREAKER_PATH,
    POLLING_STATE_PATH,
    AUTHORIZED_USERS_PATH,
)
from agents.loop.telegram_poll import (
    poll_events,
)
from agents.loop.status_display import (
    print_status,
)
from agents.loop.loop_ops import (
    is_stale,
    prune_old_loops,
    get_active_loops,
    create_loop,
)
from agents.loop.executor_dispatch import (
    _execute_event_action,
    _execute_loop_action,
)
from agents.loop.core import (
    process_once,
)

# queue_event is defined in loop.py wrapper for backward compatibility
# It will be imported from there

# Backward compatibility: re-export from store
from agents.store import bootstrap_runtime_state, STATE_DIR, RUNS_DIR


# queue_event for backward compatibility
def queue_event(text: str, priority: str = "normal", metadata: dict | None = None):
    """Queue a chat message as an event (backward compatibility)."""
    from agents.observer import observe_chat_message
    from agents.loop.state_loaders import append_to_event_queue
    event = observe_chat_message(text, priority=priority, metadata=metadata)
    append_to_event_queue(event)
    return event

__all__ = [
    # Core
    "process_once",
    
    # Circuit breaker
    "is_circuit_open",
    "get_circuit_state",
    "MAX_CONSECUTIVE_ERRORS",
    "_circuit_open",
    "_consecutive_errors",
    "_reset_circuit",
    "_reset_circuit_breaker",
    
    # Config
    "load_config",
    "executor_enabled",
    "get_executor_config",
    
    # State loaders
    "load_current_state",
    "save_current_state",
    "load_event_queue",
    "save_event_queue",
    "append_to_event_queue",
    "load_loops",
    "save_loops",
    "append_to_loops",
    "replace_or_append_loop",
    "EVENT_QUEUE_PATH",
    "LOOPS_PATH",
    "CURRENT_STATE_PATH",
    "OPEN_LOOPS_PATH",
    "CIRCUIT_BREAKER_PATH",
    "POLLING_STATE_PATH",
    "AUTHORIZED_USERS_PATH",
    
    # Telegram
    "poll_events",
    
    # Status
    "print_status",
    
    # Loop ops
    "is_stale",
    "prune_old_loops",
    "get_active_loops",
    "create_loop",
    
    # Executor dispatch
    "_execute_event_action",
    "_execute_loop_action",
    
    # Backward compatibility
    "bootstrap_runtime_state",
    "STATE_DIR",
    "RUNS_DIR",
    "queue_event",
]
