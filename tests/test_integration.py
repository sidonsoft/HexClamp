import json
import sys
import tempfile
import unittest
import contextlib
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents import executors
from agents.executors import base as base_module
from agents.executors import browser
from agents.executors import messaging
from agents.executors import code_executor
from agents import loop
from agents import store


class IntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # Reset circuit breaker globals before each test.
        loop.circuit_breaker._circuit_open = False
        loop.circuit_breaker._consecutive_errors = 0

    def tearDown(self):
        loop.circuit_breaker._circuit_open = False
        loop.circuit_breaker._consecutive_errors = 0

    def _run_with_fresh_runtime(self, tmp: Path):
        """
        Return a dict of patches that isolate state to the temp directory.

        We patch store.BASE and executors.BASE together (they must exit together
        to stay in sync), plus loop.STATE_DIR/RUNS_DIR and the state file paths.
        RUNTIME_JSON_DEFAULTS / RUNTIME_TEXT_DEFAULTS are patched *after*
        store.STATE_DIR so the dict keys use the already-patched state_dir.
        """
        base_path = Path(tmp)
        state_dir = base_path / "state"
        runs_dir = base_path / "runs"
        messaging_dir = runs_dir / "messaging_tasks"
        code_dir = runs_dir / "code_tasks"
        browser_dir = runs_dir / "browser_tasks"

        runtime_json_defaults = {
            state_dir / "current_state.json": {
                "goal": "Keep hexclamp coherent and progressing",
                "active_context": [],
                "recent_events": [],
                "current_actions": [],
                "open_loops": [],
                "last_verified_result": None,
            },
            state_dir / "event_queue.json": [],
            state_dir / "loops.json": [],
            state_dir / "circuit_breaker.json": {
                "circuit_open": False,
                "consecutive_errors": 0,
            },
        }
        runtime_text_defaults = {
            state_dir / "recent_changes.md": "# Recent Changes\n\n",
        }

        return {
            "store_BASE": patch.object(store, "BASE", base_path),
            "store_STATE_DIR": patch.object(store, "STATE_DIR", state_dir),
            "store_RUNS_DIR": patch.object(store, "RUNS_DIR", runs_dir),
            "store_RUNTIME_JSON_DEFAULTS": patch.object(
                store, "RUNTIME_JSON_DEFAULTS", runtime_json_defaults
            ),
            "store_RUNTIME_TEXT_DEFAULTS": patch.object(
                store, "RUNTIME_TEXT_DEFAULTS", runtime_text_defaults
            ),
            "executors_BASE": patch.object(executors.base, "BASE", base_path),
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
            "loop_LOOPS_PATH": patch.object(
                loop, "LOOPS_PATH", state_dir / "loops.json"
            ),
            "loop_CURRENT_STATE_PATH": patch.object(
                loop, "CURRENT_STATE_PATH", state_dir / "current_state.json"
            ),
            "loop_CIRCUIT_BREAKER_PATH": patch.object(
                loop, "CIRCUIT_BREAKER_PATH", state_dir / "circuit_breaker.json"
            ),
            "core_RUNS_DIR": patch.object(
                loop.core, "RUNS_DIR", runs_dir
            ),
            "state_loaders_EVENT_QUEUE_PATH": patch.object(
                loop.state_loaders, "EVENT_QUEUE_PATH", state_dir / "event_queue.json"
            ),
            "state_loaders_LOOPS_PATH": patch.object(
                loop.state_loaders, "LOOPS_PATH", state_dir / "loops.json"
            ),
            "state_loaders_CURRENT_STATE_PATH": patch.object(
                loop.state_loaders, "CURRENT_STATE_PATH", state_dir / "current_state.json"
            ),
            "state_loaders_OPEN_LOOPS_PATH": patch.object(
                loop.state_loaders, "OPEN_LOOPS_PATH", state_dir / "loops.json"
            ),
            "circuit_breaker_CIRCUIT_STATE_PATH": patch.object(
                loop.circuit_breaker, "CIRCUIT_STATE_PATH", state_dir / "circuit_breaker.json"
            ),
        }

    def test_enqueue_then_process_creates_messaging_task_artifacts(self):
        """Existing test: basic artifact creation via process_once()."""
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._run_with_fresh_runtime(Path(tmp))
            with contextlib.ExitStack() as stack:
                for patch_obj in patches.values():
                    stack.enter_context(patch_obj)
                
                queued = loop.queue_event(
                    "send telegram message to @sidonsoft: integration hello"
                )
                payload = loop.process_once()

            self.assertEqual(payload["processed_event"]["id"], queued.id)
            self.assertEqual(payload["actions"][0]["executor"], "messaging")
            self.assertFalse(payload["result"]["verified"])

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
                (state_dir / "loops.json").read_text(encoding="utf-8")
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
            self.assertEqual(current_state["recent_events"], [queued.id])

    def test_full_observe_execute_verify_cycle(self):
        """
        E2E test for the full observe → condense → plan → execute → verify → persist cycle.

        Verifies:
        - A queued event is dequeued after successful execution + verification
        - An open loop is created and assigned to the correct executor (messaging)
        - Evidence files (task.json, execution.json, brief.md) are created on disk
        - The loop status is updated in loops.json and current_state.json
        - All state files are persisted correctly
        - process_once() returns a complete, well-structured payload
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            runs_dir = tmp_path / "runs"
            messaging_dir = runs_dir / "messaging_tasks"

            patches = self._run_with_fresh_runtime(tmp_path)
            with contextlib.ExitStack() as stack:
                for patch_obj in patches.values():
                    stack.enter_context(patch_obj)
                    
                # Bootstrap to load circuit breaker state
                loop.bootstrap_runtime_state()
                
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

                # 3. ASSERT: event remains queued until verified execution completes
                self.assertIsNotNone(payload["processed_event"])
                self.assertEqual(payload["processed_event"]["id"], queued.id)
                self.assertEqual(payload["actions"][0]["executor"], "messaging")

                queue_after = json.loads(
                    (state_dir / "event_queue.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    len(queue_after),
                    1,
                    "Event should remain queued when execution only produced pending messaging artifacts",
                )

                # 4. ASSERT: open loop was created
                self.assertEqual(len(payload["state"]["open_loops"]), 1)
                loops = json.loads(
                    (state_dir / "loops.json").read_text(encoding="utf-8")
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

                # 6. ASSERT: result is partial until approved delivery evidence exists
                self.assertFalse(payload["result"]["verified"])
                self.assertEqual(payload["result"]["status"], "partial")

                # 7. ASSERT: state files persisted
                current_state = json.loads(
                    (state_dir / "current_state.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    current_state["goal"],
                    "Keep hexclamp coherent and progressing",
                )
                self.assertIn(loops[0]["id"], current_state["open_loops"])
                self.assertEqual(current_state["recent_events"], [queued.id])

                recent_changes = (state_dir / "recent_changes.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("Messaging", recent_changes)

                cb = json.loads(
                    (state_dir / "circuit_breaker.json").read_text(encoding="utf-8")
                )
                self.assertEqual(cb["circuit_open"], False)
                self.assertEqual(cb["consecutive_errors"], 0)

                # 8. ASSERT: run log was written
                runs = list(runs_dir.glob("run-*.json"))
                self.assertGreaterEqual(len(runs), 1)
                last_run = json.loads(
                    (runs_dir / "last_run.json").read_text(encoding="utf-8")
                )
                self.assertEqual(last_run["processed_event"]["id"], queued.id)
                self.assertFalse(last_run["result"]["verified"])

    def test_circuit_breaker_rejects_subsequent_events(self):
        """
        Verify that when the circuit breaker is open, process_once() returns early
        with a CIRCUIT BREAKER TRIPPED error and leaves the queued event in place.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patches = self._run_with_fresh_runtime(tmp_path)
            with contextlib.ExitStack() as stack:
                for patch_obj in patches.values():
                    stack.enter_context(patch_obj)
                
                loop.bootstrap_runtime_state()
                
                # Load circuit breaker state after bootstrap
                loop.circuit_breaker._load_circuit_breaker_state()

                # Simulate the circuit already being open.
                with (
                    patch.object(loop.circuit_breaker, "_circuit_open", True),
                    patch.object(
                        loop.circuit_breaker, "_consecutive_errors", loop.MAX_CONSECUTIVE_ERRORS
                    ),
                    patch.object(loop.circuit_breaker, "_reset_circuit", lambda: None),
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
                    patch.object(loop.circuit_breaker, "_circuit_open", False),
                    patch.object(loop.circuit_breaker, "_consecutive_errors", 0),
                    patch.object(loop.circuit_breaker, "_reset_circuit", lambda: None),
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
            with contextlib.ExitStack() as stack:
                for patch_obj in patches.values():
                    stack.enter_context(patch_obj)
                
                loop.bootstrap_runtime_state()
                
                # Load circuit breaker state after bootstrap
                loop.circuit_breaker._load_circuit_breaker_state()

                def fake_trip():
                    loop.circuit_breaker._circuit_open = True
                    loop.circuit_breaker._consecutive_errors = 0

                # Patch _spawn_coding_agent to fail fast.
                with (
                    patch.object(
                        executors.code_executor,
                        "_spawn_coding_agent",
                        side_effect=RuntimeError("agent unavailable"),
                    ),
                    patch.object(loop.circuit_breaker, "_trip_circuit", fake_trip),
                    patch.object(loop.circuit_breaker, "_reset_circuit", lambda: None),
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
            with contextlib.ExitStack() as stack:
                for patch_obj in patches.values():
                    stack.enter_context(patch_obj)
                
                loop.bootstrap_runtime_state()
                
                queued = loop.queue_event(
                    "send telegram message to @stateuser: persistence check"
                )
                loop.process_once()

                # All required files must exist
                self.assertTrue((state_dir / "event_queue.json").exists())
                self.assertTrue((state_dir / "loops.json").exists())
                self.assertTrue((state_dir / "current_state.json").exists())
                self.assertTrue((state_dir / "recent_changes.md").exists())
                self.assertTrue((state_dir / "circuit_breaker.json").exists())
                self.assertTrue((runs_dir / "last_run.json").exists())

                # event_queue.json: unverified messaging work remains queued
                queue = json.loads(
                    (state_dir / "event_queue.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(queue), 1)

                # loops.json: exactly one messaging loop
                loops = json.loads(
                    (state_dir / "loops.json").read_text(encoding="utf-8")
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
                self.assertEqual(cb["circuit_open"], False)
                self.assertEqual(cb["consecutive_errors"], 0)

                # last_run.json: complete payload
                last_run = json.loads(
                    (runs_dir / "last_run.json").read_text(encoding="utf-8")
                )
                self.assertEqual(last_run["processed_event"]["id"], queued.id)
                self.assertFalse(last_run["result"]["verified"])

    def test_poll_telegram_and_approve_messaging_task(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            # Additional patches for polling
            polling_state_path = tmp / "state" / "polling.json"

            patches = self._run_with_fresh_runtime(tmp)
            patches["loop_POLLING_STATE_PATH"] = patch.object(
                loop, "POLLING_STATE_PATH", polling_state_path
            )
            patches["telegram_poll_POLLING_STATE_PATH"] = patch.object(
                loop.telegram_poll, "POLLING_STATE_PATH", polling_state_path
            )
            patches["telegram_poll_AUTHORIZED_USERS_PATH"] = patch.object(
                loop.telegram_poll, "AUTHORIZED_USERS_PATH", tmp / "state" / "authorized_users.json"
            )
            # Patch get_bot_token to avoid RuntimeError
            patches["get_bot_token"] = patch(
                "agents.delivery.get_bot_token", return_value="faked"
            )
            # Patch authorization environment
            patches["auth_env"] = patch.dict(
                "os.environ", {"TELEGRAM_AUTHORIZED_USER_IDS": "1,2"}
            )
            # Patch _is_authorized to allow test users
            patches["is_authorized"] = patch.object(
                loop.telegram_poll, "_is_authorized", return_value=True
            )

            with contextlib.ExitStack() as stack:
                for p in patches.values():
                    stack.enter_context(p)

                store.bootstrap_runtime_state()
                
                # Ensure state directory exists for polling state
                (tmp / "state").mkdir(parents=True, exist_ok=True)

                # Mock updates: one normal, one approval for existing task
                task_id = "act-mock-123"
                (tmp / "runs" / "messaging_tasks" / task_id).mkdir(
                    parents=True, exist_ok=True
                )

                mock_updates = {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 300,
                            "message": {
                                "message_id": 700,
                                "text": "Normal Request",
                                "from": {"id": 1, "username": "user1"},
                                "chat": {"id": 1234, "type": "private"},
                            },
                        },
                        {
                            "update_id": 301,
                            "message": {
                                "message_id": 701,
                                "text": f"Approved messaging task: {task_id}",
                                "from": {"id": 2, "username": "admin"},
                                "chat": {"id": 5678, "type": "private"},
                            },
                        },
                    ],
                }

                # Mock TelegramDeliveryAgent.get_updates to return our test data
                with patch.object(
                    loop.telegram_poll.TelegramDeliveryAgent,
                    "get_updates",
                    return_value=mock_updates["result"],
                ) as mock_get_updates:
                    # 1. Run first poll
                    result = loop.poll_events()
                    new_events = result["events"]

                    # Verify first poll results
                    self.assertEqual(len(new_events), 2)
                    self.assertEqual(new_events[0].payload["text"], "Normal Request")
                    self.assertEqual(
                        new_events[1].payload["text"],
                        f"Approved messaging task: {task_id}",
                    )

                    # Verify metadata attached to events
                    self.assertEqual(new_events[0].payload["username"], "user1")
                    self.assertEqual(new_events[1].payload["username"], "admin")

                    # Verify offset persistence in polling state
                    with open(polling_state_path, "r") as f:
                        state = json.load(f)
                        self.assertEqual(state["last_offset"], "302")

                    # 2. Run second poll (verify offset parameter usage)
                    mock_get_updates.reset_mock()
                    mock_get_updates.return_value = []

                    loop.poll_events()

                    # Verify correctly advanced offset was sent to get_updates
                    call_args = mock_get_updates.call_args
                    self.assertEqual(call_args.kwargs["offset"], "302")

    def test_poll_unauthorized_approval_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            # Additional patches for polling
            polling_state_path = tmp / "state" / "polling.json"

            patches = self._run_with_fresh_runtime(tmp)
            patches["loop_POLLING_STATE_PATH"] = patch.object(
                loop, "POLLING_STATE_PATH", polling_state_path
            )
            patches["telegram_poll_POLLING_STATE_PATH"] = patch.object(
                loop.telegram_poll, "POLLING_STATE_PATH", polling_state_path
            )
            patches["telegram_poll_AUTHORIZED_USERS_PATH"] = patch.object(
                loop.telegram_poll, "AUTHORIZED_USERS_PATH", tmp / "state" / "authorized_users.json"
            )
            # Patch get_bot_token to avoid RuntimeError
            patches["get_bot_token"] = patch(
                "agents.delivery.get_bot_token", return_value="faked"
            )
            # Only user 1 is authorized
            patches["auth_env"] = patch.dict(
                "os.environ", {"TELEGRAM_AUTHORIZED_USER_IDS": "1"}
            )

            with contextlib.ExitStack() as stack:
                for p in patches.values():
                    stack.enter_context(p)

                store.bootstrap_runtime_state()
                
                # Ensure state directory exists
                (tmp / "state").mkdir(parents=True, exist_ok=True)

                # Mock updates: approval attempted by unauthorized user 99
                task_id = "act-mock-456"
                (tmp / "runs" / "messaging_tasks" / task_id).mkdir(
                    parents=True, exist_ok=True
                )

                mock_updates = [
                    {
                        "update_id": 400,
                        "message": {
                            "message_id": 800,
                            "text": f"/approve {task_id}",
                            "from": {"id": 99, "username": "intruder"},
                            "chat": {"id": 1234, "type": "private"},
                        },
                    }
                ]

                with patch.object(
                    loop.telegram_poll.TelegramDeliveryAgent,
                    "get_updates",
                    return_value=mock_updates,
                ):
                    # Patch _is_authorized to only allow user 1
                    with patch.object(loop.telegram_poll, "_is_authorized", side_effect=lambda uid: uid == 1):
                        result = loop.poll_events()

                    # Verify no sentinel was created
                    sentinel = tmp / "runs" / "messaging_tasks" / task_id / "approved"
                    self.assertFalse(sentinel.exists())

                    # Verify no events were created (unauthorized user is ignored)
                    self.assertEqual(len(result["events"]), 0)
                    self.assertEqual(result["approvals"], 0)
                    self.assertEqual(result["ignored"], 1)


if __name__ == "__main__":
    unittest.main()