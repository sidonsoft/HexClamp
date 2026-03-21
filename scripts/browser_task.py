#!/usr/bin/env python3
"""Browser automation helper for hexclamp.

This script is meant to be called BY OpenClaw (not as a subprocess) to execute
browser tasks. It writes task files that the main agent processes.

Usage from OpenClaw context:
    python3 /path/to/browser_task.py --task-file /path/to/task.json --result-file /path/to/result.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;!?]'
    urls = re.findall(url_pattern, text)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;!?')
        if url:
            cleaned.append(url)
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Browser task processor for hexclamp")
    parser.add_argument("--task-file", required=True, help="JSON task file to process")
    parser.add_argument("--result-file", required=True, help="Where to write results")
    
    args = parser.parse_args()
    
    task_path = Path(args.task_file)
    result_path = Path(args.result_file)
    
    if not task_path.exists():
        result = {"success": False, "error": f"Task file not found: {task_path}"}
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1
    
    task = json.loads(task_path.read_text(encoding="utf-8"))
    text = task.get("text", "")
    action_id = task.get("action_id", "unknown")
    
    # Extract URLs
    urls = extract_urls(text)
    
    result = {
        "success": True,
        "action_id": action_id,
        "task_text": text,
        "urls_found": urls,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending_execution",
        "evidence": [],
        "screenshots": [],
        "page_content": None,
        "error": None,
    }
    
    if urls:
        result["primary_url"] = urls[0]
        result["evidence"].append(f"url_extracted:{urls[0]}")
    
    # Write result for OpenClaw to pick up and execute via browser tool
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Browser task prepared: {result_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())