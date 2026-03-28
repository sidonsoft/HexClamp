from __future__ import annotations

import re
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, cast

from agents.models import Action, Event, OpenLoop
from agents.store import write_json
from agents.executors import base
from agents.executors.base import (
    _load_policies,
    _quality_gate_changed_files,
    _run_python_test,
    _write_change,
)

CODE_TASKS_DIR = base.BASE / "runs" / "code_tasks"


def _ensure_git_identity(workdir: Path) -> None:
    """Ensure git config has user.name and user.email set.
    
    If not configured globally or locally, sets defaults:
    - user.name: Hydra Claw
    - user.email: hydra@claw.ai
    """
    try:
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=5
        )
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if not name_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "Hydra Claw"],
                cwd=str(workdir),
                capture_output=True,
            )
        if not email_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "hydra@claw.ai"],
                cwd=str(workdir),
                capture_output=True,
            )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["git", "config", "user.name", "Hydra Claw"],
            cwd=str(workdir), capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "hydra@claw.ai"],
            cwd=str(workdir), capture_output=True,
        )


def _write_code_task_artifacts(
    action: Action, title: str, source_text: str, mode: str
) -> list[str]:
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
        "",
    ]
    brief = "\n".join(brief_lines)
    brief_path.write_text(brief, encoding="utf-8")

    record = {
        "action_id": action.id,
        "mode": mode,
        "title": title,
        "source_text": source_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [
            str(brief_path.relative_to(base.BASE)),
            str(record_path.relative_to(base.BASE)),
        ],
    }
    write_json(record_path, record)
    return [
        str(brief_path.relative_to(base.BASE)),
        str(record_path.relative_to(base.BASE)),
    ]


def _find_target_files(source_text: str, workspace_root: Path) -> list[Path]:
    """Extract potential target files from source text and workspace."""
    targets = []

    # Look for file paths in the text
    file_patterns = re.findall(r"[\w\-./]+\.(?:py|json|md|yaml|yml|sh)", source_text)
    for pattern in file_patterns:
        potential = workspace_root / pattern
        if potential.exists():
            targets.append(potential)

    # Look for module/function names that might indicate files
    module_patterns = re.findall(
        r"(?:in|fix|update|refactor)\s+(\w+)", source_text.lower()
    )
    for module in module_patterns:
        potential = workspace_root / f"{module}.py"
        if potential.exists():
            targets.append(potential)

    return targets


def _resolve_spawn_coding_agent():
    """Resolve the current package-level spawn hook for backward-compatible patching."""
    package = sys.modules.get("agents.executors")
    if package is not None and hasattr(package, "_spawn_coding_agent"):
        return getattr(package, "_spawn_coding_agent")
    return _spawn_coding_agent


def _spawn_coding_agent(task: str, workdir: Path, agent_id: str = "codex") -> dict:
    """
    Spawn a real coding agent to execute the task.
    Returns execution result with evidence.
    """
    result: dict[str, Any] = {
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
        task_file.write_text(
            f"# Task\n\n{task}\n\nWork in: {workdir}\n", encoding="utf-8"
        )

        # Check if we have a git repo, init if not
        git_dir = workdir / ".git"
        if not git_dir.exists():
            subprocess.run(
                ["git", "init"], cwd=str(workdir), capture_output=True, timeout=10
            )
        _ensure_git_identity(workdir)

        # Get initial git status
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10,
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

        # Build the agent command
        if agent_bin == "codex":
            cmd = ["codex", "exec", "--full-auto", task]
        elif agent_bin == "claude":
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
            timeout=300,  # 5 minute timeout
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
            timeout=10,
        )

        # Parse changed files from git status
        changed = []
        for line in status_after.stdout.strip().split("\n"):
            if line and not line.startswith("?"):
                parts = line.split()
                if len(parts) >= 2:
                    filename = parts[-1]
                    changed.append(str(workdir / filename))

        result["changed_files"] = changed
        result["evidence"].extend(
            [f"agent:{agent_bin}", f"git:modified:{len(changed)}"]
        )
        result["evidence"].append(str(task_file))

        # Verify any Python files were created/modified
        for file_path in changed:
            if file_path.endswith(".py"):
                passed, msg = _run_python_test(Path(file_path))
                if passed:
                    result["evidence"].append(f"syntax:ok:{Path(file_path).name}")
                else:
                    result["evidence"].append(
                        f"syntax:fail:{Path(file_path).name}:{msg}"
                    )

    except subprocess.TimeoutExpired:
        result["error"] = "Agent execution timed out after 5 minutes"
    except Exception as e:
        result["error"] = str(e)

    return result


def execute_code_for_event(
    action: Action, event: Event, workspace_root: Path | None = None
) -> tuple[str, list[str], list[str], OpenLoop]:
    text = event.payload.get("text", "")

    if workspace_root is None:
        workspace_root = base.store.get_workspace_root()

    task_meta_dir = CODE_TASKS_DIR / action.id
    task_meta_dir.mkdir(parents=True, exist_ok=True)

    code_artifacts = _write_code_task_artifacts(
        action, text[:80] or f"Code task {event.id}", text, "event"
    )

    policies = _load_policies()
    if policies.get("code", {}).get("require_approval", False):
        loop = OpenLoop(
            id=f"loop-{event.id}",
            title=text[:80] or f"Code follow up {event.id}",
            status="blocked",
            priority=event.priority,
            owner="code",
            created_at=event.timestamp,
            updated_at=datetime.now(timezone.utc).isoformat(),
            next_step="Awaiting explicit approval before executing code agent",
            blocked_by=["approval required"],
            evidence=[event.id, action.id, *code_artifacts],
        )
        summary = f"Code task requires approval: {text[:60]}..."
        return summary, [event.id, action.id], code_artifacts, loop

    agent_result = _resolve_spawn_coding_agent()(text, workspace_root)

    py_evidence, py_failures = _quality_gate_changed_files(
        agent_result.get("changed_files", []), workspace_root
    )

    execution_record = {
        "action_id": action.id,
        "event_id": event.id,
        "agent_result": agent_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    exec_record_path = CODE_TASKS_DIR / f"{action.id}_execution.json"
    write_json(exec_record_path, execution_record)
    code_artifacts.append(str(exec_record_path.relative_to(base.BASE)))

    evidence: list[str] = [event.id, action.id]
    evidence.extend(cast(list[str], agent_result.get("evidence", [])))
    if agent_result.get("changed_files"):
        evidence.extend(cast(list[str], agent_result["changed_files"]))
    evidence.extend(py_evidence)

    if agent_result.get("fallback"):
        stub_file = task_meta_dir / "generated.py"
        stub_content = (
            f"# Auto-generated stub (no agent available)\n# Task: {text[:80]}...\n\n"
        )
        if "function" in text.lower():
            stub_content += "def generated_function():\n    pass\n"
        else:
            stub_content += "# TODO: Implement\n"
        stub_file.write_text(stub_content, encoding="utf-8")

        loop_status = "blocked"
        next_step = f"No coding agent available. Stub created at {stub_file.name}"
        summary = f"Blocked: {agent_result['error']}. Created stub instead."
        evidence.append(str(stub_file))
    elif py_failures:
        loop_status = "blocked"
        next_step = f"Syntax error in changed files: {'; '.join(py_failures)}"
        summary = f"Agent succeeded but quality gate failed: {py_failures[0]}"
    elif agent_result["success"]:
        changed_count = len(agent_result.get("changed_files", []))
        loop_status = "resolved" if changed_count > 0 else "open"
        next_step = (
            f"Agent completed. {changed_count} file(s) modified."
            if changed_count > 0
            else "Agent completed but no files changed."
        )
        summary = f"Agent ({agent_result['agent_id']}) executed: {next_step}"
    else:
        loop_status = "blocked"
        next_step = f"Agent failed: {agent_result.get('error', 'unknown error')}"
        summary = f"Agent execution failed: {agent_result.get('error', 'unknown')}"

    policies = _load_policies()
    required_for = policies.get("verification", {}).get("required_for", [])
    has_py_compile_evidence = any("py_compile:" in e for e in evidence)
    if "code" in required_for and not has_py_compile_evidence:
        evidence.append("quality_gate:partial:no_py_compile_evidence")

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


def execute_code_for_loop(
    action: Action, loop: OpenLoop, workspace_root: Path | None = None
) -> tuple[str, list[str], list[str], OpenLoop]:
    if workspace_root is None:
        workspace_root = base.store.get_workspace_root()

    policies = _load_policies()
    if policies.get("code", {}).get("require_approval", False):
        loop.status = "blocked"
        loop.next_step = "Awaiting explicit approval before executing code agent"
        loop.blocked_by = loop.blocked_by + ["approval required"]
        loop.updated_at = datetime.now(timezone.utc).isoformat()
        code_artifacts = _write_code_task_artifacts(
            action, loop.title, loop.title, "loop"
        )
        summary = f"Code loop requires approval: {loop.title[:60]}..."
        return summary, loop.evidence, code_artifacts, loop

    agent_result = _resolve_spawn_coding_agent()(loop.title, workspace_root)

    py_evidence, py_failures = _quality_gate_changed_files(
        agent_result.get("changed_files", []), workspace_root
    )

    code_artifacts = _write_code_task_artifacts(action, loop.title, loop.title, "loop")

    execution_record = {
        "action_id": action.id,
        "loop_id": loop.id,
        "agent_result": agent_result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    exec_record_path = CODE_TASKS_DIR / f"{action.id}_execution.json"
    write_json(exec_record_path, execution_record)
    code_artifacts.append(str(exec_record_path.relative_to(base.BASE)))

    evidence: list[str] = [loop.id, action.id]
    evidence.extend(cast(list[str], agent_result.get("evidence", [])))
    if agent_result.get("changed_files"):
        evidence.extend(cast(list[str], agent_result["changed_files"]))
    evidence.extend(py_evidence)

    if agent_result.get("fallback"):
        loop.status = "blocked"
        loop.next_step = f"No coding agent available: {agent_result['error']}"
        summary = f"Loop '{loop.title}' blocked: {agent_result['error']}"
    elif py_failures:
        loop.status = "blocked"
        loop.next_step = f"Syntax error in changed files: {'; '.join(py_failures)}"
        summary = f"Loop '{loop.title}' blocked by quality gate: {py_failures[0]}"
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

    policies = _load_policies()
    required_for = policies.get("verification", {}).get("required_for", [])
    has_py_compile_evidence = any("py_compile:" in e for e in evidence)
    if "code" in required_for and not has_py_compile_evidence:
        evidence.append("quality_gate:partial:no_py_compile_evidence")

    artifact = _write_change(action, summary)

    loop.updated_at = datetime.now(timezone.utc).isoformat()
    loop.evidence = evidence
    return summary, evidence, [artifact, *code_artifacts], loop
