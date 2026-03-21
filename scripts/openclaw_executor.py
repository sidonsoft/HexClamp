#!/usr/bin/env python3
"""OpenClaw task executor - runs pending tasks using OpenClaw tools.

This script is meant to be called BY OpenClaw to execute pending tasks
using the message, browser, and other tools.

Usage from OpenClaw:
    Read and execute this script to process pending tasks.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

BASE = Path.home() / ".openclaw" / "workspace" / "hexclamp"
RUNS_DIR = BASE / "runs"


def find_pending_tasks(executor_filter: Optional[str] = None) -> list[dict]:
    """Find all pending tasks across executors."""
    pending = []
    executors = ["browser", "messaging"] if executor_filter is None else [executor_filter]
    
    for executor in executors:
        tasks_dir = RUNS_DIR / f"{executor}_tasks"
        if not tasks_dir.exists():
            continue
        
        for task_dir in tasks_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            task_file = task_dir / "task.json"
            if not task_file.exists():
                continue
            
            task_data = json.loads(task_file.read_text(encoding="utf-8"))
            if task_data.get("status") != "pending":
                continue
            
            pending.append({
                "executor": executor,
                "task_dir": task_dir,
                "task_file": task_file,
                "task": task_data,
            })
    
    return pending


def execute_browser_task(task: dict) -> dict:
    """Generate browser commands for OpenClaw to execute."""
    parsed = task["task"].get("parsed_task", {})
    urls = parsed.get("urls", [])
    
    if not urls:
        return {"success": False, "error": "No URLs found in task"}
    
    target_url = urls[0]
    
    # Return instructions for OpenClaw
    return {
        "success": True,
        "instructions": [
            f"Open URL: {target_url}",
            "Take full-page screenshot",
            "Capture page content/snapshot",
            "Save results to task directory",
        ],
        "target_url": target_url,
        "workdir": str(task["task_dir"]),
    }


def execute_messaging_task(task: dict) -> dict:
    """Generate messaging commands for OpenClaw to execute."""
    parsed = task["task"].get("parsed_task", {})
    channel = parsed.get("channel")
    recipient = parsed.get("recipient")
    content = parsed.get("content")
    requires_approval = parsed.get("requires_approval", True)
    
    if requires_approval:
        return {
            "success": False,
            "error": "Message requires approval before sending",
            "approval_needed": True,
        }
    
    if not channel or not recipient or not content:
        return {
            "success": False,
            "error": f"Missing required fields: channel={channel}, recipient={recipient}, content={content}",
        }
    
    # Return instructions for OpenClaw
    return {
        "success": True,
        "instructions": [
            f"Send {channel} message to {recipient}",
            f"Content: {content[:100]}...",
            "Capture delivery confirmation",
        ],
        "channel": channel,
        "recipient": recipient,
        "content": content,
        "workdir": str(task["task_dir"]),
    }


def generate_execution_plan() -> dict:
    """Generate an execution plan for OpenClaw."""
    pending = find_pending_tasks()
    
    plan = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pending_count": len(pending),
        "tasks": [],
    }
    
    for task in pending:
        executor = task["executor"]
        
        if executor == "browser":
            result = execute_browser_task(task)
        elif executor == "messaging":
            result = execute_messaging_task(task)
        else:
            result = {"success": False, "error": f"Unknown executor: {executor}"}
        
        plan["tasks"].append({
            "action_id": task["task"]["action_id"],
            "executor": executor,
            "workdir": str(task["task_dir"]),
            **result,
        })
    
    return plan


def print_execution_plan(plan: dict):
    """Print execution plan in a readable format."""
    print("=" * 60)
    print("HEXCLAMP EXECUTION PLAN")
    print("=" * 60)
    print(f"\nFound {plan['pending_count']} pending task(s)")
    print(f"Generated at: {plan['timestamp']}")
    
    for task in plan["tasks"]:
        print(f"\n[{task['executor'].upper()}] {task['action_id']}")
        
        if not task.get("success"):
            print(f"  Status: BLOCKED - {task.get('error', 'Unknown error')}")
            continue
        
        print("  Status: READY FOR EXECUTION")
        print("  Instructions:")
        for instr in task.get("instructions", []):
            print(f"    - {instr}")
        print(f"  Workdir: {task['workdir']}")


if __name__ == "__main__":
    plan = generate_execution_plan()
    print_execution_plan(plan)
    
    # Save plan for OpenClaw
    plan_file = RUNS_DIR / "execution_plan.json"
    with open(plan_file, "w") as f:
        json.dump(plan, f, indent=2)
    
    print(f"\nExecution plan saved to: {plan_file}")
