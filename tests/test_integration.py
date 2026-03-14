import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

import executors
import loop
import store


class IntegrationTests(unittest.TestCase):
    def test_enqueue_then_process_creates_messaging_task_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_dir = base / "state"
            runs_dir = base / "runs"
            messaging_dir = runs_dir / "messaging_tasks"

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

            with patch.object(store, "BASE", base), \
                 patch.object(store, "STATE_DIR", state_dir), \
                 patch.object(store, "RUNS_DIR", runs_dir), \
                 patch.object(store, "RUNTIME_JSON_DEFAULTS", runtime_json_defaults), \
                 patch.object(store, "RUNTIME_TEXT_DEFAULTS", runtime_text_defaults), \
                 patch.object(executors, "BASE", base), \
                 patch.object(executors, "MESSAGING_TASKS_DIR", messaging_dir), \
                 patch.object(executors, "CODE_TASKS_DIR", runs_dir / "code_tasks"), \
                 patch.object(executors, "BROWSER_TASKS_DIR", runs_dir / "browser_tasks"), \
                 patch.object(loop, "STATE_DIR", state_dir), \
                 patch.object(loop, "RUNS_DIR", runs_dir), \
                 patch.object(loop, "EVENT_QUEUE_PATH", state_dir / "event_queue.json"), \
                 patch.object(loop, "OPEN_LOOPS_PATH", state_dir / "open_loops.json"), \
                 patch.object(loop, "CURRENT_STATE_PATH", state_dir / "current_state.json"):
                queued = loop.queue_event("send telegram message to @sidonsoft: integration hello")
                payload = loop.process_once()

            self.assertEqual(payload["processed_event"]["id"], queued.id)
            self.assertEqual(payload["actions"][0]["executor"], "messaging")
            self.assertTrue(payload["result"]["verified"])

            task_dirs = list(messaging_dir.iterdir())
            self.assertEqual(len(task_dirs), 1)
            task_dir = task_dirs[0]

            task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            execution = json.loads((task_dir / "execution.json").read_text(encoding="utf-8"))
            brief = (task_dir / "brief.md").read_text(encoding="utf-8")
            loops = json.loads((state_dir / "open_loops.json").read_text(encoding="utf-8"))
            current_state = json.loads((state_dir / "current_state.json").read_text(encoding="utf-8"))

            self.assertEqual(task["parsed_task"]["recipient"], "@sidonsoft")
            self.assertEqual(task["parsed_task"]["content"], "integration hello")
            self.assertEqual(execution["target_recipient"], "@sidonsoft")
            self.assertIn("Messaging Task", brief)
            self.assertEqual(len(loops), 1)
            self.assertEqual(loops[0]["owner"], "messaging")
            self.assertIn(loops[0]["status"], {"open", "blocked"})
            self.assertIn(loops[0]["id"], current_state["open_loops"])
            self.assertEqual(current_state["recent_events"], [])


if __name__ == "__main__":
    unittest.main()
