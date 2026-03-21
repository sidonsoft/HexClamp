#!/usr/bin/env python3
"""Execute pending browser tasks for hexclamp.

This script is designed to be called BY OpenClaw (not standalone) to execute
browser tasks using the browser tool.

Usage from OpenClaw:
    Read this script and execute pending browser tasks from hexclamp.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def find_pending_browser_tasks():
    """Find all pending browser tasks in the runs directory."""
    base_dir = Path.home() / ".openclaw" / "workspace" / "hexclamp"
    browser_tasks_dir = base_dir / "runs" / "browser_tasks"
    
    if not browser_tasks_dir.exists():
        return []
    
    pending = []
    for task_dir in browser_tasks_dir.iterdir():
        if task_dir.is_dir():
            task_file = task_dir / "task.json"
            exec_file = task_dir / "execution.json"
            
            if task_file.exists():
                task_data = json.loads(task_file.read_text(encoding="utf-8"))
                if task_data.get("status") == "pending":
                    pending.append({
                        "task": task_data,
                        "task_file": task_file,
                        "exec_file": exec_file,
                        "workdir": task_dir,
                    })
    
    return pending


def generate_browser_commands(task: dict) -> list[dict]:
    """Generate browser commands for OpenClaw to execute."""
    commands = []
    
    parsed = task.get("parsed_task", {})
    urls = parsed.get("urls", [])
    
    if not urls:
        search = parsed.get("search_terms")
        if search:
            urls = [f"https://www.google.com/search?q={search.replace(' ', '+')}"]
    
    if urls:
        target_url = urls[0]
        
        # Command 1: Open the URL
        commands.append({
            "action": "open",
            "url": target_url,
            "profile": "openclaw",
        })
        
        # Command 2: Take screenshot
        commands.append({
            "action": "screenshot",
            "profile": "openclaw",
            "fullPage": True,
        })
        
        # Command 3: Get page content/snapshot
        commands.append({
            "action": "snapshot",
            "profile": "openclaw",
        })
    
    return commands


if __name__ == "__main__":
    # Find pending tasks
    tasks = find_pending_browser_tasks()
    
    if not tasks:
        print("No pending browser tasks found.")
        exit(0)
    
    print(f"Found {len(tasks)} pending browser task(s):")
    for t in tasks:
        task = t["task"]
        print(f"\n  - {task['action_id']}: {task['text'][:60]}...")
        print(f"    Target: {task['parsed_task'].get('urls', ['No URL found'])[0] if task['parsed_task'].get('urls') else 'No URL found'}")
        print(f"    Workdir: {t['workdir']}")
    
    print("\nTo execute these tasks, OpenClaw should:")
    print("1. For each task, open the target URL using browser action=open")
    print("2. Take screenshots using browser action=screenshot")
    print("3. Save results to the task workdir")
    print("4. Update task.json status to 'completed'")
