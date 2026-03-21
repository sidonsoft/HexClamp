from __future__ import annotations

import re
import ipaddress
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

from models import Action, Event, OpenLoop
from store import BASE, write_json
from .base import _write_change

BROWSER_TASKS_DIR = BASE / "runs" / "browser_tasks"


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;!?]'
    urls = re.findall(url_pattern, text)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;!?')
        if url:
            cleaned.append(url)
    return cleaned


def _parse_browser_task(text: str) -> dict:
    """Parse browser action from text."""
    text_lower = text.lower()
    
    # Extract URLs
    urls = _extract_urls(text)
    
    # Determine action type
    if "screenshot" in text_lower or "capture" in text_lower:
        action_type = "screenshot"
    elif "click" in text_lower:
        action_type = "click"
    elif "type" in text_lower or "enter" in text_lower:
        action_type = "type"
    elif "navigate" in text_lower or "goto" in text_lower or "open" in text_lower:
        action_type = "navigate"
    else:
        action_type = "navigate"
    
    # Extract search terms
    search_terms = None
    if "search" in text_lower:
        match = re.search(r'search\s+(?:for\s+)?["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            search_terms = match.group(1).strip()
    
    return {
        "type": action_type,
        "urls": urls,
        "search_terms": search_terms,
    }


def _validate_url(url: str) -> None:
    """
    Validate a URL before passing it to Playwright.
    Raises ValueError if the URL uses a dangerous scheme or targets an internal/dangerous host.
    Only http:// and https:// are allowed.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # Block dangerous schemes
    dangerous_schemes = {"javascript", "data", "file", "vbscript"}
    if scheme in dangerous_schemes:
        raise ValueError(f"URL scheme '{scheme}://' is not allowed. Only http:// and https:// are permitted. Blocked URL: {url}")

    # Only allow http and https
    if scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{scheme}://' is not allowed. Only http:// and https:// are permitted. Blocked URL: {url}")

    host = parsed.hostname or ""

    # Block localhost variations
    localhost_names = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
    if host.lower() in localhost_names:
        raise ValueError(f"Host '{host}' is not allowed (localhost). Blocked URL: {url}")

    # Block loopback (127.0.0.1 and ::1 / 0:0:0:0:0:0:0:1)
    if host == "127.0.0.1" or host == "::1" or host == "0:0:0:0:0:0:0:1":
        raise ValueError(f"Host '{host}' is not allowed (loopback). Blocked URL: {url}")

    # Use Python's ipaddress module for robust IPv4 and IPv6 validation
    ipv4_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(ipv4_pattern, host)

    if match:
        # Plain IPv4 address - validate octets are in range 0-255
        octets = [int(m) for m in match.groups()]
        if not all(0 <= o <= 255 for o in octets):
            raise ValueError(f"Host '{host}' is not a valid IPv4 address (octets must be 0-255). Blocked URL: {url}")
        # 10.x.x.x
        if octets[0] == 10:
            raise ValueError(f"Host '{host}' is not allowed (private IP range 10.x.x.x). Blocked URL: {url}")
        # 172.16.x.x - 172.31.x.x
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            raise ValueError(f"Host '{host}' is not allowed (private IP range 172.16-31.x.x). Blocked URL: {url}")
        # 192.168.x.x
        if octets[0] == 192 and octets[1] == 168:
            raise ValueError(f"Host '{host}' is not allowed (private IP range 192.168.x.x). Blocked URL: {url}")
    else:
        # Not a plain IPv4 - try parsing as IPv6 address
        try:
            addr = ipaddress.ip_address(host)
            if addr.is_loopback:
                raise ValueError(f"Host '{host}' is not allowed (loopback). Blocked URL: {url}")
            if addr.is_private:
                raise ValueError(f"Host '{host}' is not allowed (private/reserved IP range). Blocked URL: {url}")
            # Block IPv4-mapped addresses (::ffff:127.0.0.1 etc.)
            if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
                mapped_v4 = addr.ipv4_mapped
                if mapped_v4.is_loopback or mapped_v4.is_private:
                    raise ValueError(f"Host '{host}' maps to private/loopback IPv4 '{mapped_v4}'. Blocked URL: {url}")
            # Also block any address where the compressed form starts with ::ffff:
            if isinstance(addr, ipaddress.IPv6Address) and host.lower().startswith("::ffff:"):
                raise ValueError(f"Host '{host}' is not allowed (IPv4-mapped address). Blocked URL: {url}")
        except ValueError:
            # Not a valid IP address (e.g., a regular hostname) - let it pass
            pass


def _navigate_and_capture(url: str, workdir: Path) -> dict:
    """
    Launch headless Chromium, navigate to URL, capture screenshot and text.
    Returns dict with keys: success, screenshot_path, content_path, error, url, title.
    """
    try:
        from playwright.sync_api import sync_playwright

        # Validate URL before any navigation
        _validate_url(url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate with 30s timeout
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # Capture screenshot
            screenshot_path = workdir / "screenshot.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            
            # Extract visible text content
            content_path = workdir / "content.txt"
            text_content = page.inner_text("body")
            content_path.write_text(text_content, encoding="utf-8")
            
            browser.close()
            
            return {
                "success": True,
                "screenshot_path": str(screenshot_path),
                "content_path": str(content_path),
                "url": page.url,
                "title": page.title(),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "screenshot_path": None,
            "content_path": None,
            "url": url,
            "title": None,
        }


def execute_browser_for_event(action: Action, event: Event) -> tuple[str, list[str], list[str], OpenLoop]:
    text = event.payload.get("text", "")
    
    # Create browser task directory
    BROWSER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = BROWSER_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task
    task = _parse_browser_task(text)
    
    # Create task file for OpenClaw to execute
    task_file = workdir / "task.json"
    task_record = {
        "action_id": action.id,
        "event_id": event.id,
        "text": text,
        "parsed_task": task,
        "workdir": str(workdir),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(task_file, task_record)
    
    # Determine target URL
    target_url = None
    if task["urls"]:
        target_url = task["urls"][0]
    elif task["search_terms"]:
        target_url = f"https://www.google.com/search?q={quote_plus(task['search_terms'])}"
    
    # Write initial execution record
    exec_record = {
        "action_id": action.id,
        "event_id": event.id,
        "status": "pending_browser_execution",
        "target_url": target_url,
        "task_file": str(task_file),
        "workdir": str(workdir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    exec_path = workdir / "execution.json"
    write_json(exec_path, exec_record)
    
    # Create brief artifact
    brief_path = workdir / "brief.md"
    brief_content = f"# Browser Task\n\n- action_id: {action.id}\n- event_id: {event.id}\n- status: pending\n\n## Task\n\n{text}\n\n## Parsed\n\n- type: {task['type']}\n- urls: {task['urls']}\n- search_terms: {task['search_terms']}\n\n## Evidence Needed\n\n- [ ] Screenshot of page\n- [ ] Page content/text extraction\n- [ ] URL verification\n"
    brief_path.write_text(brief_content, encoding="utf-8")
    
    # Execute browser navigation if we have a URL
    evidence = [event.id, action.id]
    artifacts = [
        str(task_file.relative_to(BASE)),
        str(brief_path.relative_to(BASE)),
        str(exec_path.relative_to(BASE)),
    ]
    
    if target_url:
        browser_result = _navigate_and_capture(target_url, workdir)
        
        # Update execution record
        exec_record["status"] = "completed" if browser_result["success"] else "failed"
        exec_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        if browser_result["success"]:
            exec_record["url"] = browser_result["url"]
            exec_record["title"] = browser_result["title"]
            exec_record["screenshot_path"] = browser_result["screenshot_path"]
            exec_record["content_path"] = browser_result["content_path"]
            evidence.extend([
                str((workdir / "screenshot.png").relative_to(BASE)),
                str((workdir / "content.txt").relative_to(BASE)),
            ])
        else:
            exec_record["error"] = browser_result["error"]
        
        write_json(exec_path, exec_record)
        
        if browser_result["success"]:
            summary = f"Browser task completed: navigated to {target_url} and captured evidence"
            loop_status = "resolved"
            next_step = "Browser task executed successfully"
            blocked_by = []
        else:
            summary = f"Browser task failed: {browser_result['error']}"
            loop_status = "blocked"
            next_step = f"Browser failed: {browser_result['error'][:80]}"
            blocked_by = ["browser-navigation-failed"]
    else:
        summary = f"Browser task created but no URL found in: {text[:60]}..."
        exec_record["status"] = "failed"
        exec_record["error"] = "No URL found in task"
        write_json(exec_path, exec_record)
        loop_status = "blocked"
        next_step = "No URL found in task - requires clarification"
        blocked_by = ["no-url-found"]
    
    artifact = _write_change(action, summary)
    artifacts.append(artifact)
    
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=text[:80] or f"Browser follow up {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="browser",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=evidence,
    )
    
    return summary, evidence, artifacts, loop


def execute_browser_for_loop(action: Action, loop: OpenLoop) -> tuple[str, list[str], list[str], OpenLoop]:
    # For browser loops, execute real browser navigation with Playwright
    BROWSER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = BROWSER_TASKS_DIR / action.id
    workdir.mkdir(parents=True, exist_ok=True)
    
    # Parse the task from loop title
    task = _parse_browser_task(loop.title)
    
    # Create task file
    task_file = workdir / "task.json"
    task_record = {
        "action_id": action.id,
        "loop_id": loop.id,
        "text": loop.title,
        "parsed_task": task,
        "workdir": str(workdir),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(task_file, task_record)
    
    # Determine target URL
    target_url = None
    if task["urls"]:
        target_url = task["urls"][0]
    elif task["search_terms"]:
        target_url = f"https://www.google.com/search?q={quote_plus(task['search_terms'])}"
    
    # Write initial execution record
    exec_record = {
        "action_id": action.id,
        "loop_id": loop.id,
        "status": "pending_browser_execution",
        "target_url": target_url,
        "task_file": str(task_file),
        "workdir": str(workdir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    exec_path = workdir / "execution.json"
    write_json(exec_path, exec_record)
    
    loop.updated_at = datetime.now(timezone.utc).isoformat()
    evidence = [loop.id, action.id]
    artifacts = [
        str(task_file.relative_to(BASE)),
        str(exec_path.relative_to(BASE)),
    ]
    
    if target_url:
        browser_result = _navigate_and_capture(target_url, workdir)
        
        # Update execution record
        exec_record["status"] = "completed" if browser_result["success"] else "failed"
        exec_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        if browser_result["success"]:
            exec_record["url"] = browser_result["url"]
            exec_record["title"] = browser_result["title"]
            exec_record["screenshot_path"] = browser_result["screenshot_path"]
            exec_record["content_path"] = browser_result["content_path"]
            evidence.extend([
                str((workdir / "screenshot.png").relative_to(BASE)),
                str((workdir / "content.txt").relative_to(BASE)),
            ])
        else:
            exec_record["error"] = browser_result["error"]
        
        write_json(exec_path, exec_record)
        
        if browser_result["success"]:
            loop.status = "resolved"
            loop.next_step = "Browser task executed successfully"
            loop.blocked_by = []
            summary = f"Browser loop '{loop.title}' completed: navigated to {target_url}"
        else:
            loop.status = "blocked"
            loop.next_step = f"Browser failed: {browser_result['error'][:80]}"
            loop.blocked_by = ["browser-navigation-failed"]
            summary = f"Browser loop '{loop.title}' failed: {browser_result['error']}"
    else:
        loop.status = "blocked"
        loop.next_step = "No URL found - requires clarification"
        loop.blocked_by = ["no-url-found"]
        summary = f"Browser loop '{loop.title}' blocked: no URL found"
        exec_record["status"] = "failed"
        exec_record["error"] = "No URL found in task"
        write_json(exec_path, exec_record)
    
    loop.evidence.extend(evidence)
    artifact = _write_change(action, summary)
    artifacts.insert(0, artifact)
    
    return summary, evidence, artifacts, loop
