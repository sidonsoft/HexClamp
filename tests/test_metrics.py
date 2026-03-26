import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BASE / "scripts" / "metrics.py"

spec = importlib.util.spec_from_file_location("metrics", SCRIPT_PATH)
metrics = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = metrics
spec.loader.exec_module(metrics)


class MetricsTests(unittest.TestCase):
    def test_collect_metrics_reads_runs_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_dir = base / "state"
            runs_dir = base / "runs"
            state_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (state_dir / "current_state.json").write_text(
                json.dumps({"open_loops": ["loop-1", "loop-2"]}),
                encoding="utf-8",
            )
            (state_dir / "event_queue.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            (state_dir / "circuit_breaker.json").write_text(
                json.dumps({"consecutive_errors": 2}),
                encoding="utf-8",
            )

            (runs_dir / "run-1.json").write_text(
                json.dumps(
                    {
                        "result": {"verified": True},
                        "started_at": "2026-03-26T00:00:00+00:00",
                        "finished_at": "2026-03-26T00:00:10+00:00",
                    }
                ),
                encoding="utf-8",
            )
            (runs_dir / "run-2.json").write_text(
                json.dumps({"result": {"verified": False}}),
                encoding="utf-8",
            )

            with (
                patch.object(metrics, "STATE_DIR", state_dir),
                patch.object(metrics, "RUNS_DIR", runs_dir),
            ):
                collected = metrics.collect_metrics()

            self.assertEqual(collected.tasks_completed, 1)
            self.assertEqual(collected.verified_results, 1)
            self.assertEqual(collected.partial_results, 1)
            self.assertEqual(collected.open_loops, 2)
            self.assertEqual(collected.queued_events, 3)
            self.assertEqual(collected.circuit_breaker_trips, 2)
            self.assertEqual(collected.avg_loop_duration_seconds, 10.0)

    def test_format_dashboard_includes_core_counts(self):
        dashboard = metrics.format_dashboard(
            metrics.Metrics(
                tasks_completed=3,
                verified_results=2,
                partial_results=1,
                open_loops=4,
                queued_events=5,
                circuit_breaker_trips=1,
                avg_loop_duration_seconds=12.5,
            )
        )
        self.assertIn("HexClamp Quality Metrics", dashboard)
        self.assertIn("Tasks completed: 3", dashboard)
        self.assertIn("Average loop duration (s): 12.5", dashboard)


if __name__ == "__main__":
    unittest.main()
