"""Status display for HexClamp agent loop.

Handles printing status information to console.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone


def print_status(status: Dict[str, Any]) -> None:
    """Print formatted status to console.
    
    Args:
        status: Dict with keys like 'event', 'loop', 'actions', 'error', etc.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print(f"\n{'='*60}")
    print(f"[{timestamp}] Agent Loop Status")
    print(f"{'='*60}")
    
    # Event info
    event = status.get("processed_event")
    if event:
        event_type = event.get("event_type", "unknown")
        event_id = event.get("id", "N/A")
        print(f"Event: {event_type} (id={event_id})")
    else:
        print("Event: None")
    
    # Loop info
    loop = status.get("processed_loop")
    if loop:
        loop_id = loop.get("id", "N/A")
        loop_status = loop.get("status", "unknown")
        print(f"Loop: {loop_id} (status={loop_status})")
    else:
        print("Loop: None")
    
    # Actions
    actions = status.get("actions", [])
    if actions:
        print(f"Actions: {len(actions)}")
        for i, action in enumerate(actions[:3], 1):
            executor = action.get("executor", "unknown")
            action_type = action.get("action_type", "unknown")
            print(f"  {i}. {executor}:{action_type}")
        if len(actions) > 3:
            print(f"  ... and {len(actions) - 3} more")
    else:
        print("Actions: None")
    
    # Error
    error = status.get("error")
    if error:
        print(f"Error: {error}")
    
    # Circuit breaker
    circuit = status.get("circuit_breaker")
    if circuit:
        circuit_open = circuit.get("circuit_open", False)
        errors = circuit.get("consecutive_errors", 0)
        print(f"Circuit Breaker: {'OPEN' if circuit_open else 'CLOSED'} (errors={errors})")
    
    print(f"{'='*60}\n")
