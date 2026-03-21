import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

import store


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_runtime_state_creates_all_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_dir = base / "state"
            runs_dir = base / "runs"

            with patch.object(store, "BASE", base), \
                 patch.object(store, "STATE_DIR", state_dir), \
                 patch.object(store, "RUNS_DIR", runs_dir), \
                 patch.object(store, "RUNTIME_JSON_DEFAULTS", {
                     state_dir / "current_state.json": {
                         "goal": "Keep hexclamp coherent and progressing",
                         "active_context": [],
                         "recent_events": [],
                         "current_actions": [],
                         "open_loops": [],
                         "last_verified_result": None,
                     },
                     state_dir / "event_queue.json": [],
                     state_dir / "open_loops.json": [],
                 }), \
                 patch.object(store, "RUNTIME_TEXT_DEFAULTS", {
                     state_dir / "recent_changes.md": "# Recent Changes\n\n",
                 }):
                created = store.bootstrap_runtime_state()

            self.assertEqual(
                set(created),
                {
                    "state/current_state.json",
                    "state/event_queue.json",
                    "state/open_loops.json",
                    "state/recent_changes.md",
                },
            )
            self.assertEqual(json.loads((state_dir / "event_queue.json").read_text(encoding="utf-8")), [])
            self.assertEqual((state_dir / "recent_changes.md").read_text(encoding="utf-8"), "# Recent Changes\n\n")
            self.assertTrue(runs_dir.exists())

    def test_bootstrap_runtime_state_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_dir = base / "state"
            runs_dir = base / "runs"

            with patch.object(store, "BASE", base), \
                 patch.object(store, "STATE_DIR", state_dir), \
                 patch.object(store, "RUNS_DIR", runs_dir), \
                 patch.object(store, "RUNTIME_JSON_DEFAULTS", {
                     state_dir / "current_state.json": {"goal": "x", "active_context": [], "recent_events": [], "current_actions": [], "open_loops": [], "last_verified_result": None},
                 }), \
                 patch.object(store, "RUNTIME_TEXT_DEFAULTS", {
                     state_dir / "recent_changes.md": "# Recent Changes\n\n",
                 }):
                first = store.bootstrap_runtime_state()
                second = store.bootstrap_runtime_state()

            self.assertTrue(first)
            self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
