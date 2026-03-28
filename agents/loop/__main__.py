#!/usr/bin/env python3
"""HexClamp CLI entry point.

Usage:
    python -m agents.loop          # Run one cycle
    python -m agents.loop poll     # Poll Telegram for messages
    python -m agents.loop status   # Show current status
    python -m agents.loop enqueue <task>  # Enqueue a new task
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents.loop import (
    process_once,
    poll_events,
    queue_event,
    print_status,
    load_loops,
    load_event_queue,
)
from agents.store import STATE_DIR


def cmd_run():
    """Run one agent loop cycle."""
    result = process_once()
    print_status(result)
    return result


def cmd_poll():
    """Poll Telegram for new messages."""
    result = poll_events()
    print(f"Polled: {result.get('ignored', 0) + len(result.get('events', []))}")
    print(f"Enqueued: {len(result.get('events', []))}")
    print(f"Ignored: {result.get('ignored', 0)}")
    print(f"Approvals: {result.get('approvals', 0)}")
    return result


def cmd_status():
    """Show current system status."""
    loops = load_loops()
    events = load_event_queue()
    
    print(f"Open loops: {len(loops)}")
    print(f"Queued events: {len(events)}")
    
    if loops:
        print("\nRecent loops:")
        for loop in loops[-3:]:
            print(f"  - {loop.id}: {loop.status} - {loop.title[:50]}...")
    
    if events:
        print("\nQueued events:")
        for event in events[-3:]:
            print(f"  - {event.id}: {event.kind}")


def cmd_enqueue(task: str):
    """Enqueue a new task as an event."""
    event = queue_event(task, priority="normal")
    print(f"Enqueued event {event.id}: {task}")
    return event


def main():
    if len(sys.argv) < 2:
        # Default: run one cycle
        cmd_run()
        return
    
    command = sys.argv[1]
    
    if command == "run":
        cmd_run()
    elif command == "poll":
        cmd_poll()
    elif command == "status":
        cmd_status()
    elif command == "enqueue":
        if len(sys.argv) < 3:
            print("Usage: python -m agents.loop enqueue <task>")
            sys.exit(1)
        task = " ".join(sys.argv[2:])
        cmd_enqueue(task)
    else:
        print(f"Unknown command: {command}")
        print("Usage: python -m agents.loop [run|poll|status|enqueue]")
        sys.exit(1)


if __name__ == "__main__":
    main()
