#!/usr/bin/env python3
"""
HexClamp Self-Improvement: Fix Quote Escaping Bug
Uses MiniMax M2.7 to fix the bug in HexClamp's own task scripts
"""

import subprocess
from datetime import datetime
from pathlib import Path

task = {
    "name": "fix-quote-escaping",
    "description": "Fix quote escaping bug in HexClamp task scripts",
    "project": "~/projects/HexClamp",
    "prompt": """
Fix the quote escaping bug in HexClamp task scripts.

Problem: Multi-line prompts with quotes cause shell subprocess errors.

Files to fix:
1. scripts/remove_skills_task.py
2. scripts/overnight_scheduler.py  
3. scripts/overnight_scheduler_minimax.py
4. scripts/test_scheduler.py

Fix: Replace shell string concatenation with subprocess argument lists.

Example fix:
  # BAD:
  cmd = f"pi --model minimax '{prompt}'"
  subprocess.run(cmd, shell=True, ...)
  
  # GOOD:
  subprocess.run(["pi", "--model", "minimax", prompt], capture_output=True, text=True)

Make the changes, then show git diff and verify syntax with python3 -m py_compile.
"""
}

log_dir = Path.home() / "logs" / "zai-tasks" / "hexclamp"
log_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"{task['name']}_{timestamp}.log"

print(f"Task: {task['description']}")
print(f"Project: {task['project']}")
print(f"Log: {log_file}")
print()

cmd = ["pi", "--model", "minimax/MiniMax-M2.7", task["prompt"]]

with open(log_file, "w") as f:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(task['project']).expanduser())
    f.write(result.stdout)
    if result.stderr:
        f.write(f"\n=== STDERR ===\n{result.stderr}")

print(f"Complete! Log: {log_file}")
print()
print(result.stdout)
