"""Messaging executor - handles messaging task execution."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from models import Action, Event, OpenLoop
from store import BASE, write_json
from agents.delivery import TelegramDeliveryAgent
from .base import (
    _load_policies,
    _write_change,
)

MESSAGING_TASKS_DIR = BASE / "runs" / "messaging_tasks"


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
    at_match = re.search(r'to\s+(@[\w\-]+)', text_lower)
    if at_match:
        recipient = at_match.group(1)
    else:
        match = re.search(r'to\s+([\w\-]+)', text_lower)
        if match:
            recipient = match.group(1)
    
    # Extract content
    content = None
    content_match = re.search(r'content:\s*(.+)$', text, re.IGNORECASE | re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()
    else:
        remaining = text
        if channel:
            remaining = re.sub(rf'\b{channel}\b', '', remaining, flags=re.IGNORECASE)
        if recipient:
            remaining = remaining.replace(recipient, '')
        remaining = re.sub(r'^[\s,:\-]+|[\s,:\-]+$', '', remaining)
        if remaining and len(remaining) > 3:
            content = remaining
    
    return {
        "channel": channel,
        "recipient": recipient,
        "content": content,
        "requires_approval": False,
    }


def execute_message_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute messaging task for an event."""
    text = event.payload.get("text", "")
    
    MESSAGING_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = MESSAGING_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    task = _parse_message_task(text)
    
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
    
    brief_path = workdir / "brief.md"
    brief_content = f"# Messaging Task\n\n- action_id: {action.id}\n- event_id: {event.id}\n- status: pending\n\n## Task\n\n{text}\n\n## Parsed\n\n- channel: {task.get('channel')}\n- recipient: {task.get('recipient')}\n- content: {task.get('content', '')[:100]}\n"
    brief_path.write_text(brief_content)
    
    summary = f"Created messaging task: {task.get('channel') or 'unknown channel'} to {task.get('recipient') or 'unknown recipient'}"
    artifacts = [str(task_file.relative_to(BASE)), str(brief_path.relative_to(BASE))]
    
    from .base import _initial_loop_state
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
    
    artifact = _write_change(action, summary)
    artifacts.insert(0, artifact)
    
    return summary, [event.id], artifacts, loop


def execute_message_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute messaging task for an open loop."""
    MESSAGING_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = MESSAGING_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    task = _parse_message_task(loop.title)
    
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
    
    policies = _load_policies()
    if policies.get("external_send", {}).get("require_approval", False):
        task["requires_approval"] = True
    
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
    
    if loop_status == "blocked":
        sentinel_path = BASE / "runs" / "messaging_tasks" / action.id / "approved"
        if sentinel_path.exists():
            loop_status = "open"
            blocked_by = []
            loop.blocked_by = []
            loop.status = "open"
            next_step = f"Send {task['channel']} message to {task['recipient']}"
            summary = f"Messaging loop '{loop.title}' approved via sentinel: {task['channel']} to {task['recipient']}"
            sentinel_path.unlink()
    
    if task["channel"] == "telegram" and loop_status != "blocked" and task.get("recipient"):
        delivery_agent = TelegramDeliveryAgent()
        result = delivery_agent.send(recipient=task["recipient"], content=task["content"])
        
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
    artifacts = [str(task_file.relative_to(BASE)), str(exec_path.relative_to(BASE))]
    
    loop.updated_at = datetime.now(timezone.utc).isoformat()
    loop.status = loop_status
    loop.next_step = next_step
    loop.blocked_by = blocked_by
    loop.evidence.extend(evidence)
    
    artifact = _write_change(action, summary)
    artifacts.insert(0, artifact)
    
    return summary, evidence, artifacts, loop
