#!/usr/bin/env python3
"""
HexClamp Test Scheduler
Tests MiniMax M2.7 integration
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_test_task():
    """Run a simple test task using MiniMax M2.7"""
    log_dir = Path.home() / "logs" / "zai-tasks" / "test"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"minimax_test_{timestamp}.log"
    
    print("🧪 HexClamp Test Scheduler")
    print("==========================")
    print("Model: MiniMax M2.7")
    print(f"Log: {log_file}")
    print()
    
    # Simple test prompt
    prompt = """
This is a test of the HexClamp overnight task system using MiniMax M2.7.

Please:
1. Confirm you received this message
2. List the current date and time
3. Verify you can access the HexClamp codebase
4. Report any issues

This is a test - no actual code analysis needed.
"""
    result = subprocess.run(
        ["pi", "--model", "minimax/MiniMax-M2.7", prompt],
        cwd=Path.home() / "projects" / "HexClamp",
        capture_output=True,
        text=True
    )

    print()
    
    with open(log_file, "w") as f:
        f.write("=== STDOUT ===\n")
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)
    
    print()
    print(f"✅ Test complete!")
    print(f"Log: {log_file}")
    print()
    
    # Show output
    if result.stdout:
        print("=== Output ===")
        print(result.stdout)
    
    if result.returncode != 0:
        print(f"⚠️  Exit code: {result.returncode}")
        if result.stderr:
            print(f"Error: {result.stderr}")
    
    return log_file, result.returncode

if __name__ == "__main__":
    log_file, exit_code = run_test_task()
    sys.exit(exit_code)
