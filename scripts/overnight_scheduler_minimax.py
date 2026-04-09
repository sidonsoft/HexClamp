#!/usr/bin/env python3
"""
HexClamp Overnight Scheduler - MiniMax M2.7 Test Version
"""

import subprocess
from datetime import datetime
from pathlib import Path

# Simple test task
task = {
    "name": "minimax-test",
    "description": "MiniMax M2.7 Integration Test",
    "project": "~/projects/HexClamp",
    "prompt": """
Test task for HexClamp overnight system.

Please verify:
1. You can execute this task
2. Model is MiniMax M2.7
3. You can read files in this directory
4. Report success

List 3 files you can see in the HexClamp project.
"""
}

log_dir = Path.home() / "logs" / "zai-tasks" / "hexclamp"
log_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"{task['name']}_{timestamp}.log"

print(f"🤖 Task: {task['description']}")
print(f"📁 Project: {task['project']}")
print(f"📝 Log: {log_file}")
print()

project_dir = Path(task['project']).expanduser()
prompt = task['prompt']

with open(log_file, "w") as f:
    result = subprocess.run(
        ["pi", "--model", "minimax/MiniMax-M2.7", prompt],
        cwd=project_dir,
        capture_output=True,
        text=True
    )

    f.write(result.stdout)
    if result.stderr:
        f.write(f"\n=== STDERR ===\n{result.stderr}")

print(f"✅ Complete! Log: {log_file}")
print()
print(result.stdout)
