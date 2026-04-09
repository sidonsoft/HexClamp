#!/usr/bin/env python3
"""
HexClamp Task: Remove Agent Skills Section from sidonsoft.com
Uses MiniMax M2.7 for this straightforward edit
"""

import subprocess
from datetime import datetime
from pathlib import Path

task = {
    "name": "remove-skills-section",
    "description": "Remove agent skills section from sidonsoft.com",
    "project": "~/projects/sidonsoft-website",
    "prompt": "Remove the entire agent skills section from index.html. Find and delete the section id=skills element and all its contents. Keep everything else intact. After making the change, show git diff and verify HTML is still valid."
}

log_dir = Path.home() / "logs" / "zai-tasks" / "hexclamp"
log_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"{task['name']}_{timestamp}.log"

print(f"Task: {task['description']}")
print(f"Project: {task['project']}")
print(f"Log: {log_file}")
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

print(f"Complete! Log: {log_file}")
print()
print(result.stdout)
