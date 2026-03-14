import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BASE / "scripts" / "task_completion.py"

spec = importlib.util.spec_from_file_location("task_completion", SCRIPT_PATH)
task_completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_completion)


class TaskCompletionTests(unittest.TestCase):
    def test_verify_messaging_task_requires_sent_and_recipient(self):
        task = {
            "task": {
                "parsed_task": {"recipient": "@sidonsoft"},
                "results": {"sent": True, "delivery_confirmed": True},
            }
        }
        verification = task_completion.verify_messaging_task(task)
        self.assertTrue(verification["verified"])
        self.assertIn("✓ Message sent", verification["checks"])
        self.assertIn("✓ Delivery confirmed", verification["checks"])

    def test_verify_browser_task_needs_screenshot_and_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            screenshot = Path(tmp) / "shot.png"
            screenshot.write_bytes(b"png")
            task = {
                "task_dir": Path(tmp),
                "task": {
                    "results": {
                        "screenshot": str(screenshot),
                        "page_content": "Example Domain",
                        "url": "https://example.com",
                    }
                },
            }
            verification = task_completion.verify_browser_task(task)
            self.assertTrue(verification["verified"])
            self.assertTrue(any("Screenshot captured" in c for c in verification["checks"]))
            self.assertTrue(any("URL verified" in c for c in verification["checks"]))

    def test_verify_code_task_checks_changed_files_and_verified_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "out.py"
            changed.write_text("print('ok')\n", encoding="utf-8")
            task = {
                "task": {"action_id": "act-1"},
                "execution": {
                    "agent_result": {
                        "success": True,
                        "changed_files": [str(changed)],
                        "verified": True,
                    }
                },
            }
            verification = task_completion.verify_code_task(task)
            self.assertTrue(verification["verified"])
            self.assertIn("✓ Agent execution successful", verification["checks"])
            self.assertIn("✓ All modified files exist", verification["checks"])

    def test_update_loop_state_marks_verified_task_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            loop_file = state_dir / "open_loops.json"
            loop_file.write_text(json.dumps([
                {
                    "id": "loop-evt-123",
                    "status": "open",
                    "next_step": "Pending",
                    "blocked_by": [],
                    "evidence": [],
                    "updated_at": "2026-03-14T00:00:00+00:00",
                }
            ], indent=2), encoding="utf-8")

            task = {"task": {"event_id": "evt-123"}}
            verification = {"verified": True, "checks": ["ok"]}

            with patch.object(task_completion, "STATE_DIR", state_dir):
                task_completion.update_loop_state(task, verification, dry_run=False)

            loops = json.loads(loop_file.read_text(encoding="utf-8"))
            self.assertEqual(loops[0]["status"], "resolved")
            self.assertEqual(loops[0]["next_step"], "Task completed and verified")
            self.assertTrue(any(item.startswith("verified:") for item in loops[0]["evidence"]))


if __name__ == "__main__":
    unittest.main()
