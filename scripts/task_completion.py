#!/usr/bin/env python3
"""Task completion flow for hydra-claw-loop.

Scans pending tasks across all executors and executes them via OpenClaw tools.
Updates task status and loop state based on verification results.

Usage:
    python3 scripts/task_completion.py [--dry-run] [--executor {code,browser,message}]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent.resolve()
RUNS_DIR = BASE / "runs"
STATE_DIR = BASE / "state"


def find_pending_tasks(executor_filter: Optional[str] = None) -> list[dict]:
    """Find all pending tasks across executors."""
    pending = []
    
    executors = ["code", "browser", "messaging"] if executor_filter is None else [executor_filter]
    
    for executor in executors:
        tasks_dir = RUNS_DIR / f"{executor}_tasks"
        if not tasks_dir.exists():
            continue
        
        for task_dir in tasks_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            task_file = task_dir / "task.json"
            exec_file = task_dir / "execution.json"
            
            if not task_file.exists():
                continue
            
            task_data = json.loads(task_file.read_text(encoding="utf-8"))
            
            # Check if already completed
            if task_data.get("status") == "completed":
                continue
            
            # Load execution record if exists
            exec_data = None
            if exec_file.exists():
                exec_data = json.loads(exec_file.read_text(encoding="utf-8"))
            
            pending.append({
                "executor": executor,
                "task_dir": task_dir,
                "task_file": task_file,
                "exec_file": exec_file,
                "task": task_data,
                "execution": exec_data,
            })
    
    return pending


def verify_code_task(task: dict) -> dict:
    """Verify a code task has valid outputs."""
    result = {"verified": False, "checks": []}
    
    exec_data = task.get("execution")
    
    if not exec_data:
        result["checks"].append("No execution record found")
        return result
    
    # Check for agent result
    agent_result = exec_data.get("agent_result", {})
    
    # Verify 1: Agent completed successfully
    if agent_result.get("success"):
        result["checks"].append("✓ Agent execution successful")
    else:
        result["checks"].append("✗ Agent execution failed")
        return result
    
    # Verify 2: Changed files exist
    changed_files = agent_result.get("changed_files", [])
    if changed_files:
        result["checks"].append(f"✓ {len(changed_files)} file(s) modified")
        
        # Verify 3: Files actually exist
        all_exist = True
        for f in changed_files:
            if not Path(f).exists():
                all_exist = False
                result["checks"].append(f"✗ File not found: {f}")
        
        if all_exist:
            result["checks"].append("✓ All modified files exist")
    else:
        result["checks"].append("⚠ No files were modified")
    
    # Verify 4: Syntax check passed
    if agent_result.get("verified"):
        result["checks"].append("✓ Syntax verification passed")
        result["verified"] = True
    else:
        result["checks"].append("✗ Syntax verification failed")
    
    return result


def verify_browser_task(task: dict) -> dict:
    """Verify a browser task has captured evidence."""
    result = {"verified": False, "checks": []}
    
    task_data = task["task"]
    
    # Check for screenshot
    screenshot = task_data.get("results", {}).get("screenshot")
    if screenshot and Path(screenshot).exists():
        result["checks"].append(f"✓ Screenshot captured: {screenshot}")
        result["verified"] = True
    else:
        result["checks"].append("✗ Screenshot not found")
    
    # Check for page content
    content = task_data.get("results", {}).get("page_content")
    if content:
        result["checks"].append("✓ Page content extracted")
    else:
        result["checks"].append("⚠ No page content extracted")
    
    # Check for URL evidence
    url = task_data.get("results", {}).get("url")
    if url:
        result["checks"].append(f"✓ URL verified: {url}")
    else:
        result["checks"].append("✗ URL not recorded")
    
    return result


def verify_messaging_task(task: dict) -> dict:
    """Verify a messaging task was sent and confirmed."""
    result = {"verified": False, "checks": []}
    
    task_data = task["task"]
    
    # Check for delivery confirmation
    results = task_data.get("results", {})
    
    if results.get("sent"):
        result["checks"].append("✓ Message sent")
        result["verified"] = True
    else:
        result["checks"].append("✗ Message not sent")
    
    if results.get("delivery_confirmed"):
        result["checks"].append("✓ Delivery confirmed")
    else:
        result["checks"].append("⚠ Delivery not confirmed")
    
    # Check recipient
    recipient = task_data.get("parsed_task", {}).get("recipient")
    if recipient:
        result["checks"].append(f"✓ Recipient: {recipient}")
    else:
        result["checks"].append("✗ No recipient specified")
    
    return result


def update_loop_state(task: dict, verification: dict, dry_run: bool = False):
    """Update the associated loop based on verification results."""
    task_data = task["task"]
    event_id = task_data.get("event_id") or task_data.get("loop_id", "").replace("loop-", "")
    
    if not event_id:
        return
    
    # Find the loop file
    loop_file = STATE_DIR / "open_loops.json"
    if not loop_file.exists():
        return
    
    loops = json.loads(loop_file.read_text(encoding="utf-8"))
    
    # Find matching loop
    for loop in loops:
        if loop.get("id") == f"loop-{event_id}" or loop.get("id") == task_data.get("loop_id"):
            old_status = loop.get("status")
            
            if verification["verified"]:
                loop["status"] = "resolved"
                loop["next_step"] = "Task completed and verified"
                loop["evidence"].append(f"verified:{datetime.now(timezone.utc).isoformat()}")
            else:
                loop["status"] = "blocked"
                loop["next_step"] = "Verification failed - requires review"
                loop["blocked_by"].append("verification-failed")
            
            loop["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            if dry_run:
                print(f"  [DRY-RUN] Would update loop {loop['id']}: {old_status} → {loop['status']}")
            else:
                print(f"  Updated loop {loop['id']}: {old_status} → {loop['status']}")
            break
    
    if not dry_run:
        loop_file.write_text(json.dumps(loops, indent=2), encoding="utf-8")


def complete_task(task: dict, dry_run: bool = False):
    """Complete a single task with verification."""
    executor = task["executor"]
    task_id = task["task"]["action_id"]
    
    print(f"\n[{executor.upper()}] Task: {task_id}")
    
    # Run verification
    if executor == "code":
        verification = verify_code_task(task)
    elif executor == "browser":
        verification = verify_browser_task(task)
    elif executor == "messaging":
        verification = verify_messaging_task(task)
    else:
        print(f"  Unknown executor: {executor}")
        return
    
    # Print verification results
    for check in verification["checks"]:
        print(f"  {check}")
    
    # Update task status
    if not dry_run:
        task["task"]["status"] = "completed" if verification["verified"] else "failed"
        task["task"]["verified_at"] = datetime.now(timezone.utc).isoformat()
        task["task"]["verification"] = verification
        task["task_file"].write_text(json.dumps(task["task"], indent=2), encoding="utf-8")
    
    # Update loop state
    update_loop_state(task, verification, dry_run)
    
    return verification["verified"]


def main():
    parser = argparse.ArgumentParser(description="Complete pending hydra-claw-loop tasks")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--executor", choices=["code", "browser", "messaging"], help="Filter by executor type")
    args = parser.parse_args()
    
    print("=" * 60)
    print("HYDRA-CLAW-LOOP TASK COMPLETION FLOW")
    print("=" * 60)
    
    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")
    
    # Find pending tasks
    pending = find_pending_tasks(args.executor)
    
    if not pending:
        print("\nNo pending tasks found.")
        return 0
    
    print(f"\nFound {len(pending)} pending task(s):")
    for task in pending:
        print(f"  - [{task['executor']}] {task['task']['action_id']}")
    
    # Process each task
    completed = 0
    failed = 0
    
    for task in pending:
        if complete_task(task, args.dry_run):
            completed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {completed} completed, {failed} failed, {len(pending)} total")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
