"""Messaging executor - handles messaging task execution."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from models import Action, Event, OpenLoop
from store import write_json
from . import base
from agents.delivery import TelegramDeliveryAgent
from .base import (
    _load_policies,
    _initial_loop_state,
    _write_change,
)

MESSAGING_TASKS_DIR = base.BASE / "runs" / "messaging_tasks"


def _parse_message_task(text: str) -> dict:
    """Parse message task from text."""
    text_lower = text.lower()
    
    # Determine target channel
    channel = None
    if "telegram" in text_lower:
        channel = "telegram"
    elif "discord" in text_lower:
        channel = "discord"
    elif "signal" in text_lower:
        channel = "signal"
    elif "whatsapp" in text_lower:
        channel = "whatsapp"
    elif "email" in text_lower or "mail" in text_lower:
        channel = "email"
    
    # Determine target user/recipient
    recipient = None
    # Patterns: "to @username", "to user", "send to @username"
    # Try to match @username first, then plain username
    at_match = re.search(r'to\s+(@[\w\-]+)', text_lower)
    if at_match:
        recipient = at_match.group(1)
    else:
        # Fallback: match word after "to " but avoid "to" itself
        match = re.search(r'to\s+([\w\-]+)', text_lower)
        if match and match.group(1) not in ['to', 'send', 'message']:
            recipient = match.group(1)
    
    # Extract message content (after common prefixes)
    content = text
    # Handle "to @user: message" format
    colon_match = re.search(r'to\s+@?[\w\-]+:\s*(.+)$', text, re.IGNORECASE)
    if colon_match:
        content = colon_match.group(1).strip()
    else:
        # Remove common prefixes
        prefixes = [
            r'^send\s+(?:a\s+)?message\s+(?:to\s+)?@?[\w\-]+:?\s*',
            r'^message\s+(?:to\s+)?@?[\w\-]+:?\s*',
            r'^telegram\s+',
            r'^email\s+',
            r'^notify\s+',
        ]
        for prefix in prefixes:
            content = re.sub(prefix, '', content, flags=re.IGNORECASE)
    content = content.strip()
    
    # Check for approval keywords - default to requiring approval unless urgent/immediate
    requires_approval = not any(word in text_lower for word in ["urgent", "immediate", "now", "auto-send"])
    
    return {
        "channel": channel,
        "recipient": recipient,
        "content": content,
        "original_text": text,
        "requires_approval": requires_approval,
    }


def execute_message_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute messaging task for an event."""
    text = event.payload.get("text", "")
    
    # Create messaging task directory
    MESSAGING_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = MESSAGING_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task
    task = _parse_message_task(text)
    
    # Create task file for OpenClaw to execute
    task_file = workdir / "task.json"
    task_record = {
        "action_id": action.id,
        "event_id": event.id,
        "text": text,
        "parsed_task": task,
        "workdir": str(workdir),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(task_file, task_record)
    
    # Create brief
    brief_path = workdir / "brief.md"
    brief_content = f"""# Messaging Task

- action_id: {action.id}
- event_id: {event.id}
- status: pending

## Task

{text}

## Parsed

- channel: {task.get('channel')}
- recipient: {task.get('recipient')}
- content: {task.get('content', '')[:100]}

## Next Steps

1. Review parsed task details
2. If channel and recipient are valid, proceed with delivery
3. If missing info, ask user for clarification
"""
    brief_path.write_text(brief_content)
    
    loop_status, next_step, blocked_by, loop_summary = _initial_loop_state(event, "messaging")
    
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=event.payload.get("text", "")[:80] or f"Message task {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="messaging",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=[event.id],
    )
    
    # Add task file to evidence and artifacts
    artifact = _write_change(action, f"Created messaging task: {task['original_text'][:80]}")
    artifacts = [
        artifact,
        str(task_file.relative_to(base.BASE)),
        str(brief_path.relative_to(base.BASE)),
    ]
    evidence = [event.id, str(task_file), str(brief_path)]
    
    return loop_summary, evidence, artifacts, loop


def execute_message_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute messaging task for a loop."""
    # For message loops, create task files for OpenClaw execution
    MESSAGING_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = MESSAGING_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task from loop title
    task = _parse_message_task(loop.title)
    
    # Create task file
    task_file = workdir / "task.json"
    task_record = {
        "action_id": action.id,
        "loop_id": loop.id,
        "text": loop.title,
        "parsed_task": task,
        "workdir": str(workdir),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(task_file, task_record)
    
    # Issue #13: Enforce external_send.require_approval policy - policy overrides keyword heuristics
    policies = _load_policies()
    if policies.get("external_send", {}).get("require_approval", False):
        task["requires_approval"] = True
    
    # Determine if we can execute
    if task["requires_approval"]:
        loop_status = "blocked"
        blocked_by = ["approval required"]
        next_step = f"Await approval to send {task['channel']} message to {task['recipient']}"
        summary = f"Messaging loop '{loop.title}' queued (approval required): {task['channel']} to {task['recipient']}"
    else:
        loop_status = "open"
        blocked_by = []
        next_step = f"Send {task['channel']} message to {task['recipient']}"
        summary = f"Messaging loop '{loop.title}' ready: {task['channel']} to {task['recipient']}"
    
    # Sentinel approval check for blocked loops
    if loop_status == "blocked":
        sentinel_path = base.BASE / "runs" / "messaging_tasks" / action.id / "approved"
        if sentinel_path.exists():
            # Sentinel file found — clear blocked status and proceed
            loop_status = "open"
            blocked_by = []
            loop.blocked_by = []
            loop.status = "open"
            next_step = f"Send {task['channel']} message to {task['recipient']}"
            summary = f"Messaging loop '{loop.title}' approved via sentinel: {task['channel']} to {task['recipient']}"
            sentinel_path.unlink()
    
    # Telegram delivery: send if channel is telegram and not blocked
    if task["channel"] == "telegram" and loop_status != "blocked" and task.get("recipient"):
        delivery_agent = TelegramDeliveryAgent()
        result = delivery_agent.send(recipient=task["recipient"], content=task["content"])
        
        # Update execution record with delivery result
        exec_record = {
            "action_id": action.id,
            "loop_id": loop.id,
            "status": "pending_messaging_execution",
            "target_channel": task["channel"],
            "target_recipient": task["recipient"],
            "content_preview": task["content"][:100] if task["content"] else None,
            "requires_approval": task["requires_approval"],
            "task_file": str(task_file),
            "workdir": str(workdir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sent": result.success,
            "sent_at": datetime.now(timezone.utc).isoformat() if result.success else None,
        }
        if result.success:
            exec_record["message_id"] = result.message_id
        else:
            exec_record["error"] = result.error
        
        exec_path = workdir / "execution.json"
        write_json(exec_path, exec_record)
        
        if result.success:
            loop_status = "resolved"
            next_step = f"Message sent successfully via Telegram to {task['recipient']}"
            summary = f"Telegram message delivered to {task['recipient']}: {task['content'][:50]}..."
        else:
            loop_status = "blocked"
            blocked_by = ["delivery failed"]
            next_step = f"Telegram delivery failed: {result.error}"
            summary = f"Telegram delivery failed to {task['recipient']}: {result.error}"
    else:
        # Write execution record (no delivery attempted)
        exec_record = {
            "action_id": action.id,
            "loop_id": loop.id,
            "status": "pending_messaging_execution",
            "target_channel": task["channel"],
            "target_recipient": task["recipient"],
            "content_preview": task["content"][:100] if task["content"] else None,
            "requires_approval": task["requires_approval"],
            "task_file": str(task_file),
            "workdir": str(workdir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        exec_path = workdir / "execution.json"
        write_json(exec_path, exec_record)
    
    evidence = [loop.id, action.id, str(task_file), str(exec_path)]
    artifacts = [str(task_file.relative_to(base.BASE)), str(exec_path.relative_to(base.BASE))]
    
    loop.updated_at = datetime.now(timezone.utc).isoformat()
    loop.status = loop_status
    loop.next_step = next_step
    loop.blocked_by = blocked_by
    loop.evidence.extend(evidence)
    
    artifact = _write_change(action, summary)
    artifacts.insert(0, artifact)
    
    return summary, evidence, artifacts, loop