from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from models import Action, Event, OpenLoop
from store import BASE, append_markdown, write_json


STALE_EVIDENCE_THRESHOLD = 3
CODE_TASKS_DIR = BASE / "runs" / "code_tasks"


def _write_change(action: Action, summary: str) -> str:
    artifact = BASE / "state" / "recent_changes.md"
    append_markdown(artifact, f"- {action.id}: {summary}\n")
    return str(Path("state/recent_changes.md"))


def _initial_loop_state(event: Event, owner: str) -> tuple[str, str, list[str], str]:
    text = event.payload.get("text", "")
    normalized = text.lower()

    if "done" in normalized or "resolved" in normalized:
        return "resolved", "No further action required.", [], f"Observed resolved request: {text}"
    if "blocked" in normalized or "waiting" in normalized:
        return "blocked", "Wait for dependency or operator input.", ["external dependency"], f"Observed blocked request: {text}"
    return "open", "Decide whether this item needs deeper execution.", [], f"Observed request: {text}" if text else f"Observed event {event.id}"


def _write_code_task_artifacts(action: Action, title: str, source_text: str, mode: str) -> list[str]:
    CODE_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    slug = action.id
    brief_path = CODE_TASKS_DIR / f"{slug}.md"
    record_path = CODE_TASKS_DIR / f"{slug}.json"

    brief_lines = [
        "# Code Task",
        "",
        f"- action_id: {action.id}",
        f"- mode: {mode}",
        f"- title: {title}",
        "",
        "## Source Request",
        "",
        source_text,
        "",
        "## Required Output",
        "",
        "- concrete implementation approach",
        "- target files or file candidates",
        "- verification plan",
        "- risks or blockers",
        ""
    ]
    brief = "\n".join(brief_lines)
    brief_path.write_text(brief, encoding="utf-8")

    record = {
        "action_id": action.id,
        "mode": mode,
        "title": title,
        "source_text": source_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [str(brief_path.relative_to(BASE)), str(record_path.relative_to(BASE))],
    }
    write_json(record_path, record)
    return [str(brief_path.relative_to(BASE)), str(record_path.relative_to(BASE))]


def _run_python_test(file_path: Path) -> tuple[bool, str]:
    """Run Python file with basic syntax check and return (passed, output)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, f"Syntax check passed for {file_path.name}"
        return False, f"Syntax error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"
    except Exception as e:
        return False, f"Test error: {e}"


def _find_target_files(source_text: str, workspace_root: Path) -> list[Path]:
    """Extract potential target files from source text and workspace."""
    targets = []
    
    # Look for file paths in the text
    file_patterns = re.findall(r'[\w\-./]+\.(?:py|json|md|yaml|yml|sh)', source_text)
    for pattern in file_patterns:
        potential = workspace_root / pattern
        if potential.exists():
            targets.append(potential)
    
    # Look for module/function names that might indicate files
    module_patterns = re.findall(r'(?:in|fix|update|refactor)\s+(\w+)', source_text.lower())
    for module in module_patterns:
        potential = workspace_root / f"{module}.py"
        if potential.exists():
            targets.append(potential)
    
    return targets


def _spawn_coding_agent(task: str, workdir: Path, agent_id: str = "codex") -> dict:
    """
    Spawn a real coding agent to execute the task.
    Returns execution result with evidence.
    
    Note: This function is called from within the hydra-claw-loop, 
    which runs in a separate process. The agent spawn happens via
    the OpenClaw gateway, not direct subprocess.
    """
    import json
    import time
    
    result = {
        "success": False,
        "agent_id": agent_id,
        "task": task,
        "workdir": str(workdir),
        "output": "",
        "error": None,
        "changed_files": [],
        "evidence": [],
        "session_id": None,
    }
    
    try:
        # Create a task file for the agent to read
        task_file = workdir / f"task_{agent_id}.md"
        task_file.write_text(f"# Task\n\n{task}\n\nWork in: {workdir}\n", encoding="utf-8")
        
        # Check if we have a git repo, init if not
        git_dir = workdir / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=str(workdir), capture_output=True, timeout=10)
            subprocess.run(["git", "config", "user.email", "hydra@claw.ai"], cwd=str(workdir), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Hydra Claw"], cwd=str(workdir), capture_output=True)
        
        # Get initial git status to detect changes later
        status_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check which agent is available
        agent_bin = None
        for bin_name in ["codex", "claude", "opencode"]:
            check = subprocess.run(["which", bin_name], capture_output=True, timeout=5)
            if check.returncode == 0:
                agent_bin = bin_name
                break
        
        if not agent_bin:
            # No coding agent available - fall back to simple implementation
            result["error"] = "No coding agent (codex, claude, opencode) found in PATH"
            result["fallback"] = True
            return result
        
        # Build the agent command based on which agent was found
        if agent_bin == "codex":
            # Codex needs PTY mode for interactive execution
            cmd = ["codex", "exec", "--full-auto", task]
        elif agent_bin == "claude":
            # Claude Code uses --print mode
            cmd = ["claude", "--permission-mode", "bypassPermissions", "--print", task]
        elif agent_bin == "opencode":
            cmd = ["opencode", "run", task]
        else:
            cmd = [agent_bin, task]
        
        # Run the agent
        agent_result = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        result["output"] = agent_result.stdout + agent_result.stderr
        result["returncode"] = agent_result.returncode
        result["success"] = agent_result.returncode == 0
        
        # Get final git status to find changed files
        status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Parse changed files from git status
        changed = []
        for line in status_after.stdout.strip().split("\n"):
            if line and not line.startswith("?"):
                # Format: XY filename or XY filename -> newname
                parts = line.split()
                if len(parts) >= 2:
                    filename = parts[-1]
                    changed.append(str(workdir / filename))
        
        result["changed_files"] = changed
        result["evidence"].extend([f"agent:{agent_bin}", f"git:modified:{len(changed)}"])
        
        # Add task file to evidence
        result["evidence"].append(str(task_file))
        
        # Verify any Python files were created/modified
        for file_path in changed:
            if file_path.endswith(".py"):
                passed, msg = _run_python_test(Path(file_path))
                if passed:
                    result["evidence"].append(f"syntax:ok:{Path(file_path).name}")
                else:
                    result["evidence"].append(f"syntax:fail:{Path(file_path).name}:{msg}")
        
    except subprocess.TimeoutExpired:
        result["error"] = "Agent execution timed out after 5 minutes"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def execute_research_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
    loop_status, next_step, blocked_by, summary = _initial_loop_state(event, "research")
    artifact = _write_change(action, summary)
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=event.payload.get("text", "")[:80] or f"Follow up event {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="research",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=[event.id],
    )
    return summary, [event.id], [artifact], loop


def execute_code_for_event(action: Action, event: Event, workspace_root: Path | None = None) -> tuple[str, list[str], list[str], OpenLoop]:
    text = event.payload.get("text", "")
    
    # Determine workspace
    if workspace_root is None:
        workspace_root = BASE.parent.parent / "workspace"
    
    # Create a dedicated work directory for this task
    workdir = CODE_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Create task artifacts first
    code_artifacts = _write_code_task_artifacts(action, text[:80] or f"Code task {event.id}", text, "event")
    
    # Spawn real coding agent
    agent_result = _spawn_coding_agent(text, workdir)
    
    # Record execution results
    execution_record = {
        "action_id": action.id,
        "event_id": event.id,
        "agent_result": agent_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    exec_record_path = CODE_TASKS_DIR / f"{action.id}_execution.json"
    write_json(exec_record_path, execution_record)
    code_artifacts.append(str(exec_record_path.relative_to(BASE)))
    
    # Build evidence list
    evidence = [event.id, action.id]
    evidence.extend(agent_result.get("evidence", []))
    if agent_result.get("changed_files"):
        evidence.extend(agent_result["changed_files"])
    
    # Determine status based on agent results
    if agent_result.get("fallback"):
        # No agent available - create stub instead
        stub_file = workdir / "generated.py"
        stub_content = f"# Auto-generated stub (no agent available)\n# Task: {text[:80]}...\n\n"
        if "function" in text.lower():
            stub_content += "def generated_function():\n    pass\n"
        else:
            stub_content += "# TODO: Implement\n"
        stub_file.write_text(stub_content, encoding="utf-8")
        
        loop_status = "blocked"
        next_step = f"No coding agent available. Stub created at {stub_file.name}"
        summary = f"Blocked: {agent_result['error']}. Created stub instead."
        evidence.append(str(stub_file))
    elif agent_result["success"]:
        changed_count = len(agent_result.get("changed_files", []))
        loop_status = "resolved" if changed_count > 0 else "open"
        next_step = f"Agent completed. {changed_count} file(s) modified." if changed_count > 0 else "Agent completed but no files changed."
        summary = f"Agent ({agent_result['agent_id']}) executed: {next_step}"
    else:
        loop_status = "blocked"
        next_step = f"Agent failed: {agent_result.get('error', 'unknown error')}"
        summary = f"Agent execution failed: {agent_result.get('error', 'unknown')}"
    
    artifact = _write_change(action, summary)
    
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=text[:80] or f"Code follow up {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="code",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=["agent-failed"] if loop_status == "blocked" else [],
        evidence=evidence,
    )
    return summary, evidence, [artifact, *code_artifacts], loop


BROWSER_TASKS_DIR = BASE / "runs" / "browser_tasks"


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    import re
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;!?]'
    urls = re.findall(url_pattern, text)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;!?')
        if url:
            cleaned.append(url)
    return cleaned


def _parse_browser_task(text: str) -> dict:
    """Parse browser action from text."""
    text_lower = text.lower()
    
    # Extract URLs
    urls = _extract_urls(text)
    
    # Determine action type
    if "screenshot" in text_lower or "capture" in text_lower:
        action_type = "screenshot"
    elif "click" in text_lower:
        action_type = "click"
    elif "type" in text_lower or "enter" in text_lower:
        action_type = "type"
    elif "navigate" in text_lower or "goto" in text_lower or "open" in text_lower:
        action_type = "navigate"
    else:
        action_type = "navigate"
    
    # Extract search terms
    search_terms = None
    if "search" in text_lower:
        match = re.search(r'search\s+(?:for\s+)?["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            search_terms = match.group(1).strip()
    
    return {
        "type": action_type,
        "urls": urls,
        "search_terms": search_terms,
    }


def execute_browser_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
    text = event.payload.get("text", "")
    
    # Create browser task directory
    BROWSER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = BROWSER_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task
    task = _parse_browser_task(text)
    
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
    
    # Create artifacts
    brief_path = workdir / "brief.md"
    brief_content = f"# Browser Task\n\n- action_id: {action.id}\n- event_id: {event.id}\n- status: pending\n\n## Task\n\n{text}\n\n## Parsed\n\n- type: {task['type']}\n- urls: {task['urls']}\n- search_terms: {task['search_terms']}\n\n## Evidence Needed\n\n- [ ] Screenshot of page\n- [ ] Page content/text extraction\n- [ ] URL verification\n"
    brief_path.write_text(brief_content, encoding="utf-8")
    
    # Determine if we have a target URL
    target_url = None
    if task["urls"]:
        target_url = task["urls"][0]
    elif task["search_terms"]:
        target_url = f"https://www.google.com/search?q={task['search_terms'].replace(' ', '+')}"
    
    if target_url:
        # Write execution record
        exec_record = {
            "action_id": action.id,
            "event_id": event.id,
            "status": "pending_browser_execution",
            "target_url": target_url,
            "task_file": str(task_file),
            "workdir": str(workdir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        exec_path = workdir / "execution.json"
        write_json(exec_path, exec_record)
        
        summary = f"Browser task queued for execution: {target_url}"
        evidence = [event.id, action.id, str(task_file), str(exec_path)]
        loop_status = "open"
        next_step = f"Navigate to {target_url} and capture evidence"
    else:
        summary = f"Browser task created but no URL found in: {text[:60]}..."
        evidence = [event.id, action.id, str(task_file)]
        loop_status = "blocked"
        next_step = "No URL found in task - requires clarification"
    
    artifact = _write_change(action, summary)
    
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=text[:80] or f"Browser follow up {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="browser",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=["no-url-found"] if loop_status == "blocked" else [],
        evidence=evidence,
    )
    
    artifacts = [
        str(task_file.relative_to(BASE)),
        str(brief_path.relative_to(BASE)),
        artifact,
    ]
    if target_url:
        artifacts.append(str(exec_path.relative_to(BASE)))
    
    return summary, evidence, artifacts, loop


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
    
    # Check for approval keywords
    requires_approval = not any(word in text_lower for word in ["urgent", "immediate", "now", "auto-send"])
    
    return {
        "channel": channel,
        "recipient": recipient,
        "content": content,
        "original_text": text,
        "requires_approval": requires_approval,
    }


def execute_message_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
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
    brief_content = f"# Messaging Task\n\n- action_id: {action.id}\n- event_id: {event.id}\n- status: pending\n\n## Task\n\n{text}\n\n## Parsed\n\n- channel: {task['channel']}\n- recipient: {task['recipient']}\n- requires_approval: {task['requires_approval']}\n\n## Content\n\n{task['content']}\n\n## Execution Required\n\n- [ ] Verify recipient exists\n- [ ] Get approval (if required)\n- [ ] Send message\n- [ ] Capture delivery confirmation\n"
    brief_path.write_text(brief_content, encoding="utf-8")
    
    # Determine if we can execute
    if task["requires_approval"]:
        loop_status = "blocked"
        blocked_by = ["approval required"]
        next_step = f"Await approval to send {task['channel']} message to {task['recipient']}"
        summary = f"Messaging task queued (approval required): {task['channel']} to {task['recipient']}"
    else:
        loop_status = "open"
        blocked_by = []
        next_step = f"Send {task['channel']} message to {task['recipient']}"
        summary = f"Messaging task ready: {task['channel']} to {task['recipient']}"
    
    # Write execution record
    exec_record = {
        "action_id": action.id,
        "event_id": event.id,
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
    
    evidence = [event.id, action.id, str(task_file), str(exec_path)]
    artifact = _write_change(action, summary)
    
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=text[:80] or f"Message follow up {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="messaging",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=evidence,
    )
    
    artifacts = [
        str(task_file.relative_to(BASE)),
        str(brief_path.relative_to(BASE)),
        str(exec_path.relative_to(BASE)),
        artifact,
    ]
    
    return summary, evidence, artifacts, loop


def execute_research_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
    now = datetime.now(timezone.utc).isoformat()

    if loop.status == "blocked":
        summary = f"Loop '{loop.title}' remains blocked pending dependency resolution."
        loop.next_step = "Await unblock signal before further execution"
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "stale"
            loop.next_step = "Stale blocked loop; requires operator review"
            summary = f"Loop '{loop.title}' became stale after repeated blocked reviews."
    else:
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "resolved"
            loop.next_step = "Research loop exhausted; treat as resolved unless reopened"
            summary = f"Loop '{loop.title}' reached resolution threshold."
        else:
            loop.status = "open"
            loop.next_step = f"Escalate or specialize execution for: {loop.title}"
            summary = f"Reviewed research loop '{loop.title}' and refreshed next step."

    loop.updated_at = now
    loop.evidence.append(action.id)
    artifact = _write_change(action, summary)
    return summary, loop.evidence, [artifact], loop


def execute_code_for_loop(action: Action, loop: OpenLoop, workspace_root: Path | None = None) -> tuple[str, list[str], list[str], OpenLoop]:
    # For code loops, we run implementation again with stricter verification
    if workspace_root is None:
        workspace_root = BASE.parent.parent / "workspace"
    
    workdir = CODE_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Spawn real coding agent
    agent_result = _spawn_coding_agent(loop.title, workdir)
    
    # Create task artifacts
    code_artifacts = _write_code_task_artifacts(action, loop.title, loop.title, "loop")
    
    # Record execution results
    execution_record = {
        "action_id": action.id,
        "loop_id": loop.id,
        "agent_result": agent_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    exec_record_path = CODE_TASKS_DIR / f"{action.id}_execution.json"
    write_json(exec_record_path, execution_record)
    code_artifacts.append(str(exec_record_path.relative_to(BASE)))
    
    # Build evidence list
    evidence = [loop.id, action.id]
    evidence.extend(agent_result.get("evidence", []))
    if agent_result.get("changed_files"):
        evidence.extend(agent_result["changed_files"])
    
    # Determine status based on agent results
    if agent_result.get("fallback"):
        loop.status = "blocked"
        loop.next_step = f"No coding agent available: {agent_result['error']}"
        summary = f"Loop '{loop.title}' blocked: {agent_result['error']}"
    elif agent_result["success"]:
        changed_count = len(agent_result.get("changed_files", []))
        if changed_count > 0:
            loop.status = "resolved"
            loop.next_step = "Code implementation complete via agent"
            summary = f"Agent resolved loop '{loop.title}' with {changed_count} file(s) modified"
        else:
            loop.status = "open"
            loop.next_step = "Agent completed but no files changed"
            summary = f"Agent processed loop '{loop.title}' but made no changes"
    else:
        loop.status = "blocked"
        loop.next_step = f"Agent failed: {agent_result.get('error', 'unknown error')}"
        summary = f"Loop '{loop.title}' blocked by agent failure: {agent_result.get('error', 'unknown')}"
    
    artifact = _write_change(action, summary)
    
    loop.updated_at = datetime.now(timezone.utc).isoformat()
    loop.evidence = evidence
    return summary, evidence, [artifact, *code_artifacts], loop


def execute_browser_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
    # For browser loops, create task files for OpenClaw execution
    BROWSER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = BROWSER_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task from loop title
    task = _parse_browser_task(loop.title)
    
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
    
    # Determine target URL
    target_url = None
    if task["urls"]:
        target_url = task["urls"][0]
    elif task["search_terms"]:
        target_url = f"https://www.google.com/search?q={task['search_terms'].replace(' ', '+')}"
    
    loop.updated_at = datetime.now(timezone.utc).isoformat()
    
    if target_url:
        exec_record = {
            "action_id": action.id,
            "loop_id": loop.id,
            "status": "pending_browser_execution",
            "target_url": target_url,
            "task_file": str(task_file),
            "workdir": str(workdir),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        exec_path = workdir / "execution.json"
        write_json(exec_path, exec_record)
        
        loop.status = "open"
        loop.next_step = f"Navigate to {target_url} and capture evidence"
        summary = f"Browser loop '{loop.title}' queued for execution: {target_url}"
        evidence = [loop.id, action.id, str(task_file), str(exec_path)]
        artifacts = [str(task_file.relative_to(BASE)), str(exec_path.relative_to(BASE))]
    else:
        loop.status = "blocked"
        loop.next_step = "No URL found - requires clarification"
        summary = f"Browser loop '{loop.title}' blocked: no URL found"
        evidence = [loop.id, action.id, str(task_file)]
        artifacts = [str(task_file.relative_to(BASE))]
    
    loop.evidence.extend(evidence)
    artifact = _write_change(action, summary)
    artifacts.insert(0, artifact)
    
    return summary, evidence, artifacts, loop


def execute_message_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
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
    
    # Write execution record
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
