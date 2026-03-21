"""Tests for the browser executor (execute_browser_for_event and execute_browser_for_loop)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

import executors
import store


def _fresh_browser_patches(tmp: Path):
    """Build patch objects for a fresh temp runtime with browser tasks dir."""
    base = Path(tmp)
    state_dir = base / "state"
    runs_dir = base / "runs"
    browser_dir = runs_dir / "browser_tasks"

    runtime_json_defaults = {
        state_dir / "current_state.json": {
            "goal": "Keep hydra-claw-loop coherent and progressing",
            "active_context": [],
            "recent_events": [],
            "current_actions": [],
            "open_loops": [],
            "last_verified_result": None,
        },
        state_dir / "event_queue.json": [],
        state_dir / "open_loops.json": [],
    }
    runtime_text_defaults = {
        state_dir / "recent_changes.md": "# Recent Changes\n\n",
    }

    all_patches = [
        patch.object(store, "BASE", base),
        patch.object(store, "STATE_DIR", state_dir),
        patch.object(store, "RUNS_DIR", runs_dir),
        patch.object(store, "RUNTIME_JSON_DEFAULTS", runtime_json_defaults),
        patch.object(store, "RUNTIME_TEXT_DEFAULTS", runtime_text_defaults),
        patch.object(executors, "BASE", base),
        patch.object(executors, "BROWSER_TASKS_DIR", browser_dir),
    ]
    return all_patches, base, state_dir, browser_dir


class MockPage:
    """Minimal mock of a Playwright page."""
    def __init__(self, url="https://example.com", title="Example Domain", body_text="Hello, World!\nThis is example.com."):
        self._url = url
        self._title = title
        self._body_text = body_text

    @property
    def url(self):
        return self._url

    @property
    def title(self):
        return self._title

    def inner_text(self, selector):
        return self._body_text

    def screenshot(self, path, full_page):
        # Write a minimal valid PNG (1x1 transparent pixel)
        import struct
        # Minimal PNG: 1x1 transparent
        png_data = (
            b'\x89PNG\r\n\x1a\n'
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        Path(path).write_bytes(png_data)


class MockBrowser:
    """Minimal mock of a Playwright browser."""
    def __init__(self, page=None):
        self._page = page or MockPage()

    def new_page(self):
        return self._page

    def close(self):
        pass


def _mock_navigate_and_capture_success(url: str, workdir: Path):
    """Return a successful browser result."""
    return {
        "success": True,
        "screenshot_path": str(workdir / "screenshot.png"),
        "content_path": str(workdir / "content.txt"),
        "url": url,
        "title": "Test Page",
    }


def _mock_navigate_and_capture_failure(url: str, workdir: Path):
    """Return a failed browser result."""
    return {
        "success": False,
        "error": f"Failed to navigate to {url}: net::ERR_NAME_NOT_RESOLVED",
        "screenshot_path": None,
        "content_path": None,
        "url": url,
        "title": None,
    }


class Event:
    """Minimal mock event for testing."""
    def __init__(self, text="navigate to https://example.com", priority="normal"):
        from uuid import uuid4
        from datetime import datetime, timezone
        self.id = f"evt-{uuid4().hex[:8]}"
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.priority = priority
        self.payload = {"text": text}


class Action:
    """Minimal mock action for testing."""
    def __init__(self, action_id=None, action_type="browser"):
        from uuid import uuid4
        self.id = action_id or f"act-{uuid4().hex[:8]}"
        self.type = action_type


class OpenLoop:
    """Minimal mock open loop for testing."""
    def __init__(self, loop_id=None, title="Browser task", owner="browser", status="open", priority="normal"):
        from uuid import uuid4
        from datetime import datetime, timezone
        self.id = loop_id or f"loop-{uuid4().hex[:8]}"
        self.title = title
        self.owner = owner
        self.status = status
        self.priority = priority
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.next_step = "Initial step"
        self.blocked_by = []
        self.evidence = []


class TestExecuteBrowserForEvent(unittest.TestCase):
    """Test execute_browser_for_event with mocked browser."""

    def test_successful_navigation_creates_screenshot_and_content(self):
        """Successful browser execution creates screenshot.png and content.txt."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                # Mock the browser navigation
                with patch.object(
                    executors, "_navigate_and_capture",
                    side_effect=lambda url, workdir: _mock_navigate_and_capture_success(url, workdir)
                ):
                    # Also create the actual files
                    original_func = executors._navigate_and_capture
                    def mock_with_files(url, workdir):
                        result = _mock_navigate_and_capture_success(url, workdir)
                        # Create actual files
                        Path(result["screenshot_path"]).write_bytes(
                            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
                        )
                        Path(result["content_path"]).write_text("Example Domain\nHello, World!", encoding="utf-8")
                        return result
                    
                    with patch.object(executors, "_navigate_and_capture", side_effect=mock_with_files):
                        action = Action()
                        event = Event(text="navigate to https://example.com and take screenshot")
                        
                        summary, evidence, artifacts, loop = executors.execute_browser_for_event(action, event)
                
                # Verify loop properties
                self.assertEqual(loop.owner, "browser")
                self.assertIn(loop.status, {"resolved", "open"})
                
                # Verify task directory exists
                task_dirs = list(browser_dir.iterdir())
                self.assertEqual(len(task_dirs), 1)
                task_dir = task_dirs[0]
                
                # Verify execution.json exists and has correct status
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "completed")
                self.assertEqual(exec_data["target_url"], "https://example.com")
                
                # Verify screenshot and content files exist
                self.assertTrue((task_dir / "screenshot.png").exists())
                self.assertTrue((task_dir / "content.txt").exists())
                
                # Verify screenshot.png is a valid PNG
                png_data = (task_dir / "screenshot.png").read_bytes()
                self.assertTrue(png_data.startswith(b'\x89PNG'), "Screenshot should be a valid PNG file")
                
                # Verify content.txt has text
                content = (task_dir / "content.txt").read_text(encoding="utf-8")
                self.assertTrue(len(content) > 0, "Content should not be empty")
                
                # Verify evidence includes screenshot and content
                screenshot_evidence = [e for e in evidence if "screenshot.png" in e]
                content_evidence = [e for e in evidence if "content.txt" in e]
                self.assertTrue(len(screenshot_evidence) > 0, "Evidence should include screenshot.png")
                self.assertTrue(len(content_evidence) > 0, "Evidence should include content.txt")

    def test_failed_navigation_sets_status_to_failed(self):
        """Failed browser navigation sets execution status to 'failed' with error."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                with patch.object(
                    executors, "_navigate_and_capture",
                    side_effect=lambda url, workdir: _mock_navigate_and_capture_failure(url, workdir)
                ):
                    action = Action()
                    event = Event(text="navigate to https://this-domain-does-not-exist-xyz.com")
                    
                    summary, evidence, artifacts, loop = executors.execute_browser_for_event(action, event)
            
                # Verify loop is blocked
                self.assertEqual(loop.status, "blocked")
                self.assertTrue(len(loop.blocked_by) > 0)
                
                # Verify task directory exists
                task_dirs = list(browser_dir.iterdir())
                self.assertEqual(len(task_dirs), 1)
                task_dir = task_dirs[0]
                
                # Verify execution.json has failed status
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "failed")
                self.assertIn("error", exec_data)
                
                # Verify screenshot and content were NOT created
                self.assertFalse((task_dir / "screenshot.png").exists())
                self.assertFalse((task_dir / "content.txt").exists())

    def test_no_url_found_blocks_loop(self):
        """Event with no URL marks loop as blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                action = Action()
                event = Event(text="do some browser stuff")  # No URL
                
                summary, evidence, artifacts, loop = executors.execute_browser_for_event(action, event)
            
                self.assertEqual(loop.status, "blocked")
                self.assertIn("no-url-found", loop.blocked_by)
                
                # Verify execution record has failed status
                task_dirs = list(browser_dir.iterdir())
                task_dir = task_dirs[0]
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "failed")


class TestExecuteBrowserForLoop(unittest.TestCase):
    """Test execute_browser_for_loop with mocked browser."""

    def test_successful_navigation_updates_loop_to_resolved(self):
        """Successful browser execution marks loop as resolved."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                def mock_with_files(url, workdir):
                    result = _mock_navigate_and_capture_success(url, workdir)
                    Path(result["screenshot_path"]).write_bytes(
                        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
                    )
                    Path(result["content_path"]).write_text("Example Domain content", encoding="utf-8")
                    return result
                
                with patch.object(executors, "_navigate_and_capture", side_effect=mock_with_files):
                    action = Action()
                    loop = OpenLoop(
                        title="navigate to https://example.com and capture",
                        owner="browser",
                    )
                    
                    summary, evidence, artifacts, updated_loop = executors.execute_browser_for_loop(action, loop)
                
                self.assertEqual(updated_loop.status, "resolved")
                self.assertIn("screenshot.png", " ".join(evidence))
                self.assertIn("content.txt", " ".join(evidence))
                
                # Verify task dir
                task_dirs = list(browser_dir.iterdir())
                self.assertEqual(len(task_dirs), 1)
                task_dir = task_dirs[0]
                
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "completed")
                self.assertTrue((task_dir / "screenshot.png").exists())
                self.assertTrue((task_dir / "content.txt").exists())

    def test_failed_navigation_marks_loop_blocked(self):
        """Failed browser execution marks loop as blocked with error."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                with patch.object(
                    executors, "_navigate_and_capture",
                    side_effect=lambda url, workdir: _mock_navigate_and_capture_failure(url, workdir)
                ):
                    action = Action()
                    loop = OpenLoop(
                        title="navigate to https://bad-domain-xyz123.invalid",
                        owner="browser",
                    )
                    
                    summary, evidence, artifacts, updated_loop = executors.execute_browser_for_loop(action, loop)
                
                self.assertEqual(updated_loop.status, "blocked")
                
                # Verify execution record
                task_dirs = list(browser_dir.iterdir())
                task_dir = task_dirs[0]
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "failed")
                self.assertIn("error", exec_data)

    def test_no_url_found_blocks_loop(self):
        """Loop with no URL marks loop as blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            p, base, state_dir, browser_dir = _fresh_browser_patches(tmp)
            with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
                action = Action()
                loop = OpenLoop(
                    title="take a screenshot in the browser",  # No URL
                    owner="browser",
                )
                
                summary, evidence, artifacts, updated_loop = executors.execute_browser_for_loop(action, loop)
            
                self.assertEqual(updated_loop.status, "blocked")
                task_dirs = list(browser_dir.iterdir())
                task_dir = task_dirs[0]
                exec_data = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_data["status"], "failed")


class TestURLValidation(unittest.TestCase):
    """Test URL validation blocks dangerous schemes and internal hosts."""

    def test_blocks_javascript_scheme(self):
        """javascript: URLs must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("javascript:alert('xss')")
        self.assertIn("javascript", str(ctx.exception).lower())
        self.assertIn("not allowed", str(ctx.exception))

    def test_blocks_data_scheme(self):
        """data: URLs must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("data:text/html,<script>alert('xss')</script>")
        self.assertIn("data", str(ctx.exception).lower())
        self.assertIn("not allowed", str(ctx.exception))

    def test_blocks_file_scheme(self):
        """file:// URLs must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("file:///etc/passwd")
        self.assertIn("file", str(ctx.exception).lower())
        self.assertIn("not allowed", str(ctx.exception))

    def test_blocks_vbscript_scheme(self):
        """vbscript: URLs must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("vbscript:MsgBox('xss')")
        self.assertIn("vbscript", str(ctx.exception).lower())
        self.assertIn("not allowed", str(ctx.exception))

    def test_blocks_localhost(self):
        """localhost must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("http://localhost:8080/admin")
        self.assertIn("localhost", str(ctx.exception).lower())

    def test_blocks_127_0_0_1(self):
        """127.0.0.1 must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("http://127.0.0.1:8080/admin")
        self.assertIn("127.0.0.1", str(ctx.exception))

    def test_blocks_10_x_x_x(self):
        """10.x.x.x private range must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("http://10.0.0.5:8080/admin")
        self.assertIn("10.", str(ctx.exception).lower())
        self.assertIn("private", str(ctx.exception).lower())

    def test_blocks_192_168_x_x(self):
        """192.168.x.x private range must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("http://192.168.1.100/admin")
        self.assertIn("192.168.", str(ctx.exception).lower())
        self.assertIn("private", str(ctx.exception).lower())

    def test_blocks_172_16_31_x_x(self):
        """172.16-31.x.x private range must be rejected."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("http://172.20.50.100/admin")
        self.assertIn("172.", str(ctx.exception).lower())
        self.assertIn("private", str(ctx.exception).lower())

    def test_allows_https_url(self):
        """Valid https:// URLs must pass validation."""
        executors._validate_url("https://example.com")
        executors._validate_url("https://www.google.com/search?q=test")

    def test_allows_http_url(self):
        """Valid http:// URLs must pass validation."""
        executors._validate_url("http://example.com")

    def test_validate_url_error_includes_blocked_url(self):
        """ValueError message must include the blocked URL for auditability."""
        with self.assertRaises(ValueError) as ctx:
            executors._validate_url("javascript:alert('xss')")
        self.assertIn("javascript:alert", str(ctx.exception))


class TestNavigateAndCaptureRejectsDangerousURLs(unittest.TestCase):
    """_navigate_and_capture must return success=False for dangerous URLs."""

    def test_dangerous_url_returns_failure(self):
        """javascript: URL must produce a failure result, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = executors._navigate_and_capture("javascript:alert(1)", workdir)
            self.assertFalse(result["success"])
            self.assertIn("error", result)
            self.assertIsNone(result["screenshot_path"])
            self.assertIsNone(result["content_path"])

    def test_localhost_url_returns_failure(self):
        """localhost URL must produce a failure result, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = executors._navigate_and_capture("http://localhost:8080/admin", workdir)
            self.assertFalse(result["success"])
            self.assertIn("error", result)

    def test_private_ip_url_returns_failure(self):
        """Private IP URL must produce a failure result, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            result = executors._navigate_and_capture("http://192.168.1.100/admin", workdir)
            self.assertFalse(result["success"])
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
