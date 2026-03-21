import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

import executors
import executors.base
import executors.browser
import executors.messaging
import executors.code_executor
import loop
import store


class IntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # Reset circuit breaker globals before each test.
        loop._circuit_open = False
        loop._consecutive_errors = 0

    def tearDown(self):
        loop._circuit_open = False
        loop._consecutive_errors = 0

    def _run_with_fresh_runtime(self, tmp: Path):
        """
        Return a dict of patches that isolate state to the temp directory.

        We patch store.BASE and executors.BASE together (they must exit together
        to stay in sync), plus loop.STATE_DIR/RUNS_DIR and the state file paths.
        RUNTIME_JSON_DEFAULTS / RUNTIME_TEXT_DEFAULTS are patched *after*
        store.STATE_DIR so the dict keys use the already-patched state_dir.
        """
        base = Path(tmp)
        state_dir = base / "state"
        runs_dir = base / "runs"
        messaging_dir = runs_dir / "messaging_tasks"
        code_dir = runs_dir / "code_tasks"
        browser_dir = runs_dir / "browser_tasks"

        runtime_json_defaults = {
            state_dir
            / "current_state.json": {
                "goal": "Keep hexclamp coherent and progressing",
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

        return {
            "store_BASE": patch.object(store, "BASE", base),
            "store_STATE_DIR": patch.object(store, "STATE_DIR", state_dir),
            "store_RUNS_DIR": patch.object(store, "RUNS_DIR", runs_dir),
            "store_RUNTIME_JSON_DEFAULTS": patch.object(
                store, "RUNTIME_JSON_DEFAULTS", runtime_json_defaults
            ),
            "store_RUNTIME_TEXT_DEFAULTS": patch.object(
                store, "RUNTIME_TEXT_DEFAULTS", runtime_text_defaults
            ),
            "executors_BASE": patch.object(executors.base, "BASE", base),
            "executors_MESSAGING_TASKS_DIR": patch.object(
                executors.messaging, "MESSAGING_TASKS_DIR", messaging_dir
            ),
            "executors_CODE_TASKS_DIR": patch.object(
                executors.code_executor, "CODE_TASKS_DIR", code_dir
            ),
            "executors_BROWSER_TASKS_DIR": patch.object(
                executors.browser, "BROWSER_TASKS_DIR", browser_dir
            ),
            "loop_STATE_DIR": patch.object(loop, "STATE_DIR", state_dir),
            "loop_RUNS_DIR": patch.object(loop, "RUNS_DIR", runs_dir),
            "loop_EVENT_QUEUE_PATH": patch.object(
                loop, "EVENT_QUEUE_PATH", state_dir / "event_queue.json"
            ),
            "loop_OPEN_LOOPS_PATH": patch.object(
                loop, "OPEN_LOOPS_PATH", state_dir / "open_loops.json"
            ),
            "loop_CURRENT_STATE_PATH": patch.object(
                loop, "CURRENT_STATE_PATH", state_dir / "current_state.json"
            ),
            "loop_CIRCUIT_BREAKER_PATH": patch.object(
                loop, "CIRCUIT_BREAKER_PATH", state_dir / "circuit_breaker.json"
            ),
        }

    def test_enqueue_then_process_creates_messaging_task_artifacts(self):
        """Existing test: basic artifact creation via process_once()."""
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._run_with_fresh_runtime(Path(tmp))
            with (
                patches["store_BASE"],
                patches["store_STATE_DIR"],
                patches["store_RUNS_DIR"],
                patches["store_RUNTIME_JSON_DEFAULTS"],
                patches["store_RUNTIME_TEXT_DEFAULTS"],
                patches["executors_BASE"],
                patches["executors_MESSAGING_TASKS_DIR"],
                patches["executors_CODE_TASKS_DIR"],
                patches["executors_BROWSER_TASKS_DIR"],
                patches["loop_STATE_DIR"],
                patches["loop_RUNS_DIR"],
                patches["loop_EVENT_QUEUE_PATH"],
                patches["loop_OPEN_LOOPS_PATH"],
                patches["loop_CURRENT_STATE_PATH"],
                patches["loop_CIRCUIT_BREAKER_PATH"],
            ):
                queued = loop.queue_event(
                    "send telegram message to @sidonsoft: integration hello"
                )
                payload = loop.process_once()

            self.assertEqual(payload["processed_event"]["id"], queued.id)
            self.assertEqual(payload["actions"][0]["executor"], "messaging")
            self.assertTrue(payload["result"]["verified"])

            state_dir = Path(tmp) / "state"
            runs_dir = Path(tmp) / "runs"
            messaging_dir = runs_dir / "messaging_tasks"
            task_dirs = list(messaging_dir.iterdir())
            self.assertEqual(len(task_dirs), 1)
            task_dir = task_dirs[0]

            task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            execution = json.loads(
                (task_dir / "execution.json").read_text(encoding="utf-8")
            )
            brief = (task_dir / "brief.md").read_text(encoding="utf-8")
            loops = json.loads(
                (state_dir / "open_loops.json").read_text(encoding="utf-8")
            )
            current_state = json.loads(
                (state_dir / "current_state.json").read_text(encoding="utf-8")
            )

            self.assertEqual(task["parsed_task"]["recipient"], "@sidonsoft")
            self.assertEqual(task["parsed_task"]["content"], "integration hello")
            self.assertEqual(execution["target_recipient"], "@sidonsoft")
            self.assertIn("Messaging Task", brief)
            self.assertEqual(len(loops), 1)
            self.assertEqual(loops[0]["owner"], "messaging")
            self.assertIn(loops[0]["status"], {"open", "blocked"})
            self.assertIn(loops[0]["id"], current_state["open_loops"])
            self.assertEqual(current_state["recent_events"], [])

    def test_full_observe_execute_verify_cycle(self):
        """
        E2E test for the full observe → condense → plan → execute → verify → persist cycle.

        Verifies:
        - A queued event is dequeued after successful execution + verification
        - An open loop is created and assigned to the correct executor (messaging)
        - Evidence files (task.json, execution.json, brief.md) are created on disk
        - The loop status is updated in open_loops.json and current_state.json
        - All state files are persisted correctly
        - process_once() returns a complete, well-structured payload
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            runs_dir = tmp_path / "runs"
            messaging_dir = runs_dir / "messaging_tasks"

            patches = self._run_with_fresh_runtime(tmp_path)
            with (
                patches["store_BASE"],
                patches["store_STATE_DIR"],
                patches["store_RUNS_DIR"],
                patches["store_RUNTIME_JSON_DEFAULTS"],
                patches["store_RUNTIME_TEXT_DEFAULTS"],
                patches["executors_BASE"],
                patches["executors_MESSAGING_TASKS_DIR"],
                patches["executors_CODE_TASKS_DIR"],
                patches["executors_BROWSER_TASKS_DIR"],
                patches["loop_STATE_DIR"],
                patches["loop_RUNS_DIR"],
                patches["loop_EVENT_QUEUE_PATH"],
                patches["loop_OPEN_LOOPS_PATH"],
                patches["loop_CURRENT_STATE_PATH"],
                patches["loop_CIRCUIT_BREAKER_PATH"],
            ):
                # 1. Inject a real event into the queue
                queued = loop.queue_event(
                    "send telegram message to @testuser: check system status"
                )
                self.assertIsNotNone(queued.id)
                self.assertEqual(queued.priority, "normal")

                # Verify event is in the queue on disk
                queue_on_disk = json.loads(
                    (state_dir / "event_queue.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(queue_on_disk), 1)
                self.assertEqual(queue_on_disk[0]["id"], queued.id)

                # 2. Execute ONE process_once() cycle
                payload = loop.process_once()

                # 3. ASSERT: event was dequeued
                self.assertIsNotNone(payload["processed_event"])
                self.assertEqual(payload["processed_event"]["id"], queued.id)
                self.assertEqual(payload["actions"][0]["executor"], "messaging")

                queue_after = json.loads(
                    (state_dir / "event_queue.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    len(queue_after),
                    0,
                    "Event should be dequeued after successful execution+verification",
                )

                # 4. ASSERT: open loop was created
                self.assertEqual(len(payload["state"]["open_loops"]), 1)
                loops = json.loads(
                    (state_dir / "open_loops.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(loops), 1)
                self.assertEqual(loops[0]["owner"], "messaging")
                self.assertIn(loops[0]["status"], {"open", "blocked"})
                self.assertIn(loops[0]["id"], payload["state"]["open_loops"])

                # 5. ASSERT: evidence files exist on disk
                task_dirs = list(messaging_dir.iterdir())
                self.assertEqual(len(task_dirs), 1)
                task_dir = task_dirs[0]
                self.assertTrue((task_dir / "task.json").exists())
                self.assertTrue((task_dir / "brief.md").exists())
                self.assertTrue((task_dir / "execution.json").exists())

                task_data = json.loads(
                    (task_dir / "task.json").read_text(encoding="utf-8")
                )
                self.assertEqual(task_data["parsed_task"]["recipient"], "@testuser")
                self.assertEqual(
                    task_data["parsed_task"]["content"], "check system status"
                )

                exec_data = json.loads(
                    (task_dir / "execution.json").read_text(encoding="utf-8")
                )
                self.assertEqual(exec_data["target_recipient"], "@testuser")
                self.assertIn(
                    "Messaging Task",
                    (task_dir / "brief.md").read_text(encoding="utf-8"),
                )

                # 6. ASSERT: result is verified
                self.assertTrue(payload["result"]["verified"])
                self.assertEqual(payload["result"]["status"], "success")

                # 7. ASSERT: state files persisted
                current_state = json.loads(
                    (state_dir / "current_state.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    current_state["goal"],
                    "Keep hexclamp coherent and progressing",
                )
                self.assertIn(loops[0]["id"], current_state["open_loops"])
                self.assertEqual(current_state["recent_events"], [])

                recent_changes = (state_dir / "recent_changes.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("Messaging", recent_changes)

                cb = json.loads(
                    (state_dir / "circuit_breaker.json").read_text(encoding="utf-8")
                )
                self.assertEqual(cb["open"], False)
                self.assertEqual(cb["consecutive_errors"], 0)

                # 8. ASSERT: run log was written
                runs = list(runs_dir.glob("run-*.json"))
                self.assertGreaterEqual(len(runs), 1)
                last_run = json.loads(
                    (runs_dir / "last_run.json").read_text(encoding="utf-8")
                )
                self.assertEqual(last_run["processed_event"]["id"], queued.id)
                self.assertTrue(last_run["result"]["verified"])

    def test_circuit_breaker_rejects_subsequent_events(self):
        """
        Verify that when the circuit breaker is open, process_once() returns early
        with a CIRCUIT BREAKER TRIPPED error and leaves the queued event in place.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patches = self._run_with_fresh_runtime(tmp_path)
            with (
                patches["store_BASE"],
                patches["store_STATE_DIR"],
                patches["store_RUNS_DIR"],
                patches["store_RUNTIME_JSON_DEFAULTS"],
                patches["store_RUNTIME_TEXT_DEFAULTS"],
                patches["executors_BASE"],
                patches["executors_MESSAGING_TASKS_DIR"],
                patches["executors_CODE_TASKS_DIR"],
                patches["executors_BROWSER_TASKS_DIR"],
                patches["loop_STATE_DIR"],
                patches["loop_RUNS_DIR"],
                patches["loop_EVENT_QUEUE_PATH"],
                patches["loop_OPEN_LOOPS_PATH"],
                patches["loop_CURRENT_STATE_PATH"],
                patches["loop_CIRCUIT_BREAKER_PATH"],
            ):
                loop.bootstrap_runtime_state()

                # Simulate the circuit already being open.
                with (
                    patch.object(loop, "_circuit_open", True),
                    patch.object(
                        loop, "_consecutive_errors", loop.MAX_CONSECUTIVE_ERRORS
                    ),
                    patch.object(loop, "_reset_circuit", lambda: None),
                ):
                    loop.queue_event(
                        "send telegram message to @user: should be rejected"
                    )
                    payload = loop.process_once()

                    self.assertIsNone(payload["processed_event"])
                    self.assertIsNone(payload["processed_loop"])
                    self.assertEqual(payload["actions"], [])
                    self.assertIsNone(payload["result"])
                    self.assertIn("CIRCUIT BREAKER TRIPPED", payload["error"])

                    # Event must still be in the queue
                    state_dir = tmp_path / "state"
                    queue = json.loads(
                        (state_dir / "event_queue.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(len(queue), 1)

                    # Run log was written with error
                    runs_dir = tmp_path / "runs"
                    last_run = json.loads(
                        (runs_dir / "last_run.json").read_text(encoding="utf-8")
                    )
                    self.assertIn("CIRCUIT BREAKER TRIPPED", last_run["error"])

                # After resetting, events should process normally
                with (
                    patch.object(loop, "_circuit_open", False),
                    patch.object(loop, "_consecutive_errors", 0),
                    patch.object(loop, "_reset_circuit", lambda: None),
                ):
                    payload = loop.process_once()
                    self.assertIsNotNone(payload["processed_event"])
                    self.assertEqual(payload["actions"][0]["executor"], "messaging")

    def test_circuit_breaker_trips_after_consecutive_failures(self):
        """
        Verify that after MAX_CONSECUTIVE_ERRORS exceptions in process_once(),
        the circuit breaker trips and subsequent events are rejected.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patches = self._run_with_fresh_runtime(tmp_path)
            with (
                patches["store_BASE"],
                patches["store_STATE_DIR"],
                patches["store_RUNS_DIR"],
                patches["store_RUNTIME_JSON_DEFAULTS"],
                patches["store_RUNTIME_TEXT_DEFAULTS"],
                patches["executors_BASE"],
                patches["executors_MESSAGING_TASKS_DIR"],
                patches["executors_CODE_TASKS_DIR"],
                patches["executors_BROWSER_TASKS_DIR"],
                patches["loop_STATE_DIR"],
                patches["loop_RUNS_DIR"],
                patches["loop_EVENT_QUEUE_PATH"],
                patches["loop_OPEN_LOOPS_PATH"],
                patches["loop_CURRENT_STATE_PATH"],
                patches["loop_CIRCUIT_BREAKER_PATH"],
            ):
                loop.bootstrap_runtime_state()

                def fake_trip():
                    loop._circuit_open = True
                    loop._consecutive_errors = 0

                # Patch _spawn_coding_agent to fail fast.
                with (
                    patch.object(
                        executors,
                        "_spawn_coding_agent",
                        side_effect=RuntimeError("agent unavailable"),
                    ),
                    patch.object(loop, "_trip_circuit", fake_trip),
                    patch.object(loop, "_reset_circuit", lambda: None),
                ):
                    for i in range(3):
                        loop.queue_event(f"fix the bug in module_{i}.py")

                    # First two: fail but circuit not yet open
                    p1 = loop.process_once()
                    self.assertIsNone(p1["processed_event"])
                    self.assertIn("agent unavailable", p1["error"])

                    p2 = loop.process_once()
                    self.assertIsNone(p2["processed_event"])
                    self.assertIn("agent unavailable", p2["error"])

                    # Third: circuit should trip
                    p3 = loop.process_once()
                    self.assertIsNone(p3["processed_event"])
                    self.assertIn("CIRCUIT BREAKER TRIPPED", p3["error"])

    def test_state_files_persisted_after_cycle(self):
        """
        Verify that after a successful process_once() cycle, all required state files
        exist and contain the correct data.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            runs_dir = tmp_path / "runs"
            patches = self._run_with_fresh_runtime(tmp_path)
            with (
                patches["store_BASE"],
                patches["store_STATE_DIR"],
                patches["store_RUNS_DIR"],
                patches["store_RUNTIME_JSON_DEFAULTS"],
                patches["store_RUNTIME_TEXT_DEFAULTS"],
                patches["executors_BASE"],
                patches["executors_MESSAGING_TASKS_DIR"],
                patches["executors_CODE_TASKS_DIR"],
                patches["executors_BROWSER_TASKS_DIR"],
                patches["loop_STATE_DIR"],
                patches["loop_RUNS_DIR"],
                patches["loop_EVENT_QUEUE_PATH"],
                patches["loop_OPEN_LOOPS_PATH"],
                patches["loop_CURRENT_STATE_PATH"],
                patches["loop_CIRCUIT_BREAKER_PATH"],
            ):
                queued = loop.queue_event(
                    "send telegram message to @stateuser: persistence check"
                )
                loop.process_once()

                # All required files must exist
                self.assertTrue((state_dir / "event_queue.json").exists())
                self.assertTrue((state_dir / "open_loops.json").exists())
                self.assertTrue((state_dir / "current_state.json").exists())
                self.assertTrue((state_dir / "recent_changes.md").exists())
                self.assertTrue((state_dir / "circuit_breaker.json").exists())
                self.assertTrue((runs_dir / "last_run.json").exists())

                # event_queue.json: event was dequeued
                queue = json.loads(
                    (state_dir / "event_queue.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(queue), 0)

                # open_loops.json: exactly one messaging loop
                loops = json.loads(
                    (state_dir / "open_loops.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(loops), 1)
                self.assertEqual(loops[0]["owner"], "messaging")

                # current_state.json: open_loops contains the loop id
                state = json.loads(
                    (state_dir / "current_state.json").read_text(encoding="utf-8")
                )
                self.assertIn(loops[0]["id"], state["open_loops"])

                # circuit_breaker.json: closed, no errors
                cb = json.loads(
                    (state_dir / "circuit_breaker.json").read_text(encoding="utf-8")
                )
                self.assertEqual(cb["open"], False)
                self.assertEqual(cb["consecutive_errors"], 0)

                # last_run.json: complete payload
                last_run = json.loads(
                    (runs_dir / "last_run.json").read_text(encoding="utf-8")
                )
                self.assertEqual(last_run["processed_event"]["id"], queued.id)
                self.assertTrue(last_run["result"]["verified"])


if __name__ == "__main__":
    unittest.main()
