"""Core agent loop for HexClamp.

Main process_once() function implementing the Observe → Condense → Plan → Execute → Verify → Persist cycle.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.store import (
    RUNS_DIR,
    write_json,
    bootstrap_runtime_state,
    ensure_dirs,
)
from agents.models import CurrentState, Event, OpenLoop, Action
from agents.condenser import condense_with_handoff, load_handoff, condense_state
from agents.planner import plan_next_actions

from agents.loop.circuit_breaker import (
    is_circuit_open,
    _reset_circuit,
    _trip_circuit,
    _persist_circuit_breaker_state,
    get_circuit_state,
    MAX_CONSECUTIVE_ERRORS,
    _consecutive_errors,
)
from agents.loop.state_loaders import (
    load_current_state,
    save_current_state,
    load_event_queue,
    save_event_queue,
    load_loops,
    replace_or_append_loop,
    append_to_loops,
)
from agents.loop.loop_ops import prune_old_loops
from agents.loop.executor_dispatch import _execute_event_action, _execute_loop_action
from agents.loop.status_display import print_status


def _write_run_result(payload: Dict[str, Any]) -> None:
    """Write run result to disk."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    write_json(RUNS_DIR / f"run-{timestamp}.json", payload)
    write_json(RUNS_DIR / "last_run.json", payload)


def process_once() -> Dict[str, Any]:
    """Execute one iteration of the agent loop.
    
    Returns:
        Dict with keys: processed_event, processed_loop, state, actions, result, error, circuit_breaker
    """
    global _consecutive_errors
    
    # Circuit breaker: return early if open
    if is_circuit_open():
        payload: Dict[str, Any] = {
            "processed_event": None,
            "processed_loop": None,
            "state": None,
            "actions": [],
            "result": None,
            "error": "CIRCUIT BREAKER TRIPPED — loop halted",
            "circuit_breaker": get_circuit_state(),
        }
        _write_run_result(payload)
        return payload

    ensure_dirs()
    bootstrap_runtime_state()

    # Load handoff if exists (from previous condensation)
    handoff = load_handoff()
    
    # Load current state
    current_state = load_current_state()
    
    # Load event queue - PEEK at first event (don't pop yet)
    events = load_event_queue()
    event = events[0] if events else None
    
    # Load loops
    loops = load_loops()
    loop = loops[-1] if loops else None
    
    # Process event if present
    processed_event = None
    processed_loop = None
    actions: List[Action] = []
    result = None
    error = None
    
    try:
        if event:
            processed_event = event
            
            # Condense event into state
            if current_state:
                current_state = condense_state([event], loops, current_state)
            else:
                current_state = condense_state([event], loops)
            
            # Plan action for event
            actions_list = plan_next_actions([event], loops)
            if actions_list:
                actions.extend(actions_list)
                result = _execute_event_action(actions_list[0], event)
                
                # Extract OpenLoop from result if present (e.g., from messaging executor)
                # Result tuple format: (summary, evidence, artifacts, loop)
                if isinstance(result, tuple) and len(result) >= 4:
                    from agents.models import OpenLoop
                    loop_obj = result[3]  # Loop is 4th element (index 3)
                    if isinstance(loop_obj, OpenLoop):
                        loops.append(loop_obj)
                        replace_or_append_loop(loop_obj)
                        # Update current state with new loop
                        if current_state:
                            current_state.open_loops.append(loop_obj.id)
        
        # Process loop if present
        elif loop:
            processed_loop = loop
            
            # Check if loop is complete
            if loop.status == "complete":
                loops.pop()  # Remove completed loop
            else:
                # Condense loop progress
                if current_state:
                    current_state = condense_state([], [loop], current_state)
                
                # Plan next action for loop
                actions_list = plan_next_actions([], [loop])
                if actions_list:
                    actions.extend(actions_list)
                    result = _execute_loop_action(actions_list[0], loop)
                    
                    # Update loop with result
                    if hasattr(loop, 'results'):
                        loop.results.append(result)
                    loop.updated_at = datetime.now(timezone.utc)
                    replace_or_append_loop(loop)
        
        # Remove event from queue only if successfully processed AND verified
        # (or if no messaging task was created)
        if event and events and events[0].id == event.id:
            # Check if result indicates pending verification
            should_remove = True
            if result:
                # If result is a dict with verified=False, keep event in queue
                if isinstance(result, dict) and result.get('verified') == False:
                    should_remove = False
                # If result is a tuple (legacy), check verified field
                elif isinstance(result, tuple) and len(result) > 0:
                    # Legacy tuple format doesn't have verified, assume pending
                    should_remove = False
            
            if should_remove:
                events.pop(0)
        
        # Save state
        if current_state:
            save_current_state(current_state)
        
        # Save event queue
        save_event_queue(events)
        
        # Prune old loops periodically
        prune_old_loops()
        
        # Success - reset circuit breaker and persist state
        _reset_circuit()
        _consecutive_errors = 0
        _persist_circuit_breaker_state()
        
    except Exception as e:
        error = str(e)
        _consecutive_errors += 1
        if _consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            _trip_circuit()
            # Circuit just tripped - override error with circuit breaker message
            error = "CIRCUIT BREAKER TRIPPED — loop halted"
        _persist_circuit_breaker_state()
        # Clear processed event/loop on error - they weren't successfully processed
        event = None
        loop = None
    
    # Build result payload
    def _serialize_result(r):
        """Serialize result to JSON-serializable format."""
        if isinstance(r, dict):
            return r
        if hasattr(r, 'to_dict'):
            return r.to_dict()
        if isinstance(r, tuple):
            # Convert tuple to dict (for legacy executor returns)
            # Tuple format: (message, event_ids, action_ids, file_paths, open_loop)
            result_dict = {
                "message": str(r[0]) if len(r) > 0 else None,
                "verified": False,  # Messaging tasks require approval
                "status": "partial",  # Pending approval
            }
            if len(r) > 4 and hasattr(r[4], 'to_dict'):
                result_dict["open_loop"] = r[4].to_dict()
            return result_dict
        return {"result": str(r), "verified": False, "status": "partial"}
    
    payload = {
        "processed_event": event.to_dict() if event else None,
        "processed_loop": loop.to_dict() if loop else None,
        "state": current_state.to_dict() if current_state else None,
        "actions": [a.to_dict() for a in actions],
        "result": _serialize_result(result),
        "error": error,
        "circuit_breaker": get_circuit_state(),
    }
    
    # Persist run result
    _write_run_result(payload)
    
    # Print status
    print_status(payload)
    
    return payload
