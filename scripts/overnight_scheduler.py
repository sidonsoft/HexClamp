#!/usr/bin/env python3
"""
HexClamp Overnight Task Scheduler
Runs complex analysis tasks during off-peak hours using GLM-5.1
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Task definitions
TASKS = {
    "monday": {
        "name": "architecture-review",
        "description": "HexClamp Architecture Review",
        "project": "~/projects/HexClamp",
        "prompt": """
Analyze the architecture of this codebase. Review all Python files in agents/, core/, and config/.

Identify:
1. Architectural bottlenecks
2. Circular dependencies  
3. Event loop efficiency issues
4. Agent isolation problems
5. State management concerns
6. Error handling patterns

Create ARCHITECTURE_REVIEW.md with specific refactor recommendations.
""",
        "est_prompts": 80
    },
    "tuesday": {
        "name": "circuit-breaker",
        "description": "Circuit Breaker Analysis",
        "project": "~/projects/HexClamp",
        "prompt": """
Review the circuit breaker implementation.

Identify:
1. Edge cases not handled
2. Race conditions
3. Failure scenarios
4. Boundary conditions

Create CIRCUIT_BREAKER_ANALYSIS.md with findings and recommendations.
""",
        "est_prompts": 50
    },
    "friday": {
        "name": "accessibility",
        "description": "Website Accessibility Audit",
        "project": "~/projects/sidonsoft-website",
        "prompt": """
Audit index.html for WCAG 2.1 AA accessibility compliance.

Check:
1. Semantic HTML
2. ARIA labels
3. Color contrast
4. Keyboard navigation
5. Screen reader compatibility

Create ACCESSIBILITY_AUDIT.md with issues and fixes.
""",
        "est_prompts": 40
    },
    "sunday": {
        "name": "ad-hoc",
        "description": "Buffer/Ad-Hoc Complex Tasks",
        "project": "~",
        "prompt": "Check ~/.pi/agent/workspace/docs/zai-weekly-plan.md for ad-hoc tasks",
        "est_prompts": 100
    }
}

def get_day_name():
    """Get current day name (lowercase)"""
    return datetime.now().strftime("%A").lower()

def run_task(task_name, project, prompt):
    """Run a task using .pi with GLM-5.1"""
    log_dir = Path.home() / "logs" / "zai-tasks" / "hexclamp"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{task_name}_{timestamp}.log"
    
    print(f"🤖 HexClamp Overnight Task: {task_name}")
    print(f"📁 Project: {project}")
    print(f"📝 Log: {log_file}")
    print()
    
    # Run .pi with GLM-5.1
    project_dir = Path(project).expanduser()

    with open(log_file, "w") as f:
        result = subprocess.run(
            ["pi", "--model", "zai/GLM-5.1", prompt],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
    
    
    print(f"✅ Task complete! Log: {log_file}")
    return log_file

def main():
    day = get_day_name()
    
    if day not in TASKS:
        print(f"ℹ️  No task scheduled for {day}")
        return
    
    task = TASKS[day]
    print(f"📅 {day.capitalize()} Task: {task['description']}")
    print(f"🧠 Model: GLM-5.1 (off-peak, 1× quota)")
    print(f"📊 Est. prompts: {task['est_prompts']}")
    print()
    
    run_task(task["name"], task["project"], task["prompt"])

if __name__ == "__main__":
    main()
