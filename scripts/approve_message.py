#!/usr/bin/env python3
"""Approve and execute pending messaging tasks.

Usage:
    python3 scripts/approve_message.py <task_id> [--execute]
    python3 scripts/approve_message.py --list
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent.resolve()
MESSAGING_DIR = BASE / "runs" / "messaging_tasks"


def list_pending_messages():
    """List all pending messaging tasks."""
    if not MESSAGING_DIR.exists():
        print("No messaging tasks found.")
        return

    pending = []
    for task_dir in MESSAGING_DIR.iterdir():
        if not task_dir.is_dir():
            continue

        task_file = task_dir / "task.json"
        if not task_file.exists():
            continue

        task_data = json.loads(task_file.read_text(encoding="utf-8"))
        if task_data.get("status") != "pending":
            continue

        parsed = task_data.get("parsed_task", {})
        pending.append({
            "task_id": task_data.get("task_id", task_dir.name),
            "channel": parsed.get("channel"),
            "recipient": parsed.get("recipient"),
            "content_preview": parsed.get("content", "")[:60],
            "requires_approval": parsed.get("requires_approval", True),
        })
    
    if not pending:
        print("No pending messaging tasks found.")
        return

    print(f"\nFound {len(pending)} pending message(s):\n")
    for msg in pending:
        status = "[APPROVAL REQUIRED]" if msg["requires_approval"] else "[READY]"
        print(f"  {msg['task_id']}")
        print(f"    {status} {msg['channel']} → {msg['recipient']}")
        print(f"    Content: {msg['content_preview']}...")
        print()


def _resolve_task_dir(task_id: str) -> Path:
    base_dir = MESSAGING_DIR.resolve()
    task_dir = (MESSAGING_DIR / task_id).resolve()
    try:
        task_dir.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Invalid task id: {task_id}")
    return task_dir


def approve_message(task_id: str, execute: bool = False) -> bool:
    """Approve a message for sending."""
    try:
        task_dir = _resolve_task_dir(task_id)
    except ValueError as exc:
        print(f"Error: {exc}")
        return False
    task_file = task_dir / "task.json"

    if not task_file.exists():
        print(f"Error: Task {task_id} not found")
        return False

    task_data = json.loads(task_file.read_text(encoding="utf-8"))

    if task_data.get("status") != "pending":
        print(f"Error: Task {task_id} is not pending (status: {task_data.get('status')})")
        return False

    # Mark as approved
    task_data["parsed_task"]["requires_approval"] = False
    task_data["approved_at"] = datetime.now(timezone.utc).isoformat()
    task_file.write_text(json.dumps(task_data, indent=2), encoding="utf-8")
    
    print(f"✓ Task {task_id} approved for sending")
    
    if execute:
        print("  Executing message send...")
        # In a real implementation, this would trigger the actual send
        # For now, mark as ready for OpenClaw execution
        exec_file = task_dir / "execution.json"
        if exec_file.exists():
            exec_data = json.loads(exec_file.read_text(encoding="utf-8"))
            exec_data["approved"] = True
            exec_data["approved_at"] = task_data["approved_at"]
            exec_file.write_text(json.dumps(exec_data, indent=2), encoding="utf-8")
        print("  ✓ Ready for OpenClaw execution")

    return True


def main():
    parser = argparse.ArgumentParser(description="Approve messaging tasks")
    parser.add_argument("task_id", nargs="?", help="Stable messaging task ID to approve")
    parser.add_argument("--list", "-l", action="store_true", help="List pending messages")
    parser.add_argument("--execute", "-x", action="store_true", help="Execute after approval")
    args = parser.parse_args()
    if args.list or not args.task_id:
        list_pending_messages()
        return 0

    if approve_message(args.task_id, args.execute):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
