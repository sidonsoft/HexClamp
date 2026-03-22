from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, cast

import yaml
from pathlib import Path

from agents import store
from agents.condenser import condense_state
from agents.executors import (
    execute_browser_for_event,
    execute_browser_for_loop,
    execute_code_for_event,
    execute_code_for_loop,
    execute_message_for_event,
    execute_message_for_loop,
    execute_research_for_event,
    execute_research_for_loop,
)
from agents.observer import observe_chat_message
from agents.store import (
    RUNS_DIR,
    STATE_DIR,
    append_json_array,
    bootstrap_runtime_state,
    ensure_dirs,
    get_workspace_root,
    read_json,
    write_json,
)

WORKSPACE_ROOT = get_workspace_root()
from agents.models import CurrentState, Event, OpenLoop

MAX_CONSECUTIVE_ERRORS = 3
_circuit_open = False
_consecutive_errors = 0

CIRCUIT_BREAKER_PATH = STATE_DIR / "circuit_breaker.json"


def _load_circuit_breaker_state() -> None:
    """Load circuit breaker state from disk, if available."""
    global _circuit_open, _consecutive_errors
    try:
        data = read_json(CIRCUIT_BREAKER_PATH, default=None)
        if data is not None:
            _circuit_open = bool(data.get("open", False))
            _consecutive_errors = int(data.get("consecutive_errors", 0))
    except Exception:
        pass  # Ignore corrupt state files; start fresh


def _persist_circuit_breaker_state() -> None:
    """Persist circuit breaker state to disk."""
    write_json(
        CIRCUIT_BREAKER_PATH,
        {"open": _circuit_open, "consecutive_errors": _consecutive_errors},
    )


from agents.store import _parse_datetime
from agents.planner import plan_next_actions, rank_open_loops, STALE_THRESHOLD_HOURS
from agents.validate import validate_payload
from agents.verifier import verify_result


EVENT_QUEUE_PATH = STATE_DIR / "event_queue.json"
OPEN_LOOPS_PATH = STATE_DIR / "open_loops.json"
CURRENT_STATE_PATH = STATE_DIR / "current_state.json"
POLLING_STATE_PATH = STATE_DIR / "polling_state.json"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _executor_enabled(executor: str) -> bool:
    if executor == "system":
        return False  # system executor is not supported
    enabled = True
    for config_path in (
        store.BASE / "config" / "agents.yaml",
        store.BASE / "config" / "policies.yaml",
    ):
        try:
            data = _load_yaml(config_path)
        except Exception:
            import warnings

            warnings.warn(f"Could not read {config_path}; ignoring", RuntimeWarning)
            continue
        value = data.get("executors", {}).get(executor, {}).get("enabled")
        if value is not None:
            enabled = enabled and bool(value)
    return enabled


def _reset_circuit():
    global _circuit_open, _consecutive_errors
    _circuit_open = False
    _consecutive_errors = 0
    _persist_circuit_breaker_state()


def _trip_circuit():
    global _circuit_open, _consecutive_errors
    _circuit_open = True
    _consecutive_errors = 0
    _persist_circuit_breaker_state()


def prune_old_loops(open_loops: List[OpenLoop]) -> List[OpenLoop]:
    """Remove loops older than STALE_THRESHOLD_HOURS from open_loops."""
    return [loop for loop in open_loops if not _is_loop_stale(loop)]


def _is_loop_stale(loop: OpenLoop) -> bool:
    """Check if loop is stale based on time since creation."""
    try:
        updated = _parse_datetime(loop.updated_at)
    except ValueError:
        # Invalid timestamp = treat as stale so it gets pruned
        return True
    now = datetime.now(timezone.utc)
    hours_since = (now - updated).total_seconds() / 3600
    return bool(hours_since > STALE_THRESHOLD_HOURS)


def load_current_state() -> CurrentState:
    data = read_json(CURRENT_STATE_PATH)
    if not data:
        return CurrentState(goal="Keep hexclamp coherent and progressing")
    return CurrentState(**data)


def load_event_queue() -> List[Event]:
    data = read_json(EVENT_QUEUE_PATH, default=[])
    for item in data:
        validate_payload(item, "event.schema.json")
    return [Event(**item) for item in data]


def save_event_queue(events: List[Event]) -> None:
    payload = [event.to_dict() for event in events]
    validate_payload(payload, "event-queue.schema.json")
    write_json(EVENT_QUEUE_PATH, payload)


def load_open_loops() -> List[OpenLoop]:
    data = read_json(OPEN_LOOPS_PATH, default=[])
    for item in data:
        validate_payload(item, "loop.schema.json")
    return [OpenLoop(**item) for item in data]


def save_open_loops(open_loops: List[OpenLoop]) -> None:
    payload = [loop.to_dict() for loop in open_loops]
    validate_payload(payload, "open-loops.schema.json")
    write_json(OPEN_LOOPS_PATH, payload)


def _is_authorized(sender_id: int | None) -> bool:
    """Check if a Telegram sender ID is authorized to perform administrative actions."""
    import os

    if not sender_id:
        return False
    auth_env = os.environ.get("TELEGRAM_AUTHORIZED_USER_IDS", "")
    if not auth_env:
        return False
    try:
        authorized_ids = [int(i.strip()) for i in auth_env.split(",") if i.strip()]
        return sender_id in authorized_ids
    except ValueError:
        return False


def queue_event(
    text: str, priority: str = "normal", metadata: dict | None = None
) -> Event:
    event = observe_chat_message(text, priority=priority, metadata=metadata)
    append_json_array(EVENT_QUEUE_PATH, event.to_dict())
    return event


def poll_events() -> dict:
    """Poll Telegram for new messages and enqueue them as events."""
    from agents.delivery import TelegramDeliveryAgent

    # Load offset
    state = read_json(POLLING_STATE_PATH, default={"last_offset": None})
    offset = state.get("last_offset")

    agent = TelegramDeliveryAgent()
    updates = agent.get_updates(offset=offset)

    events = []
    ignored = 0
    approvals = 0
    max_update_id = offset

    for update in updates:
        update_id = update.get("update_id")
        if max_update_id is None or update_id >= max_update_id:
            max_update_id = update_id + 1

        message = update.get("message")
        if not message or "text" not in message:
            ignored += 1
            continue

        text = message.get("text")
        sender = message.get("from", {})
        chat = message.get("chat", {})

        # Convert to event with metadata for traceability
        metadata = {
            "telegram": {
                "update_id": update_id,
                "message_id": message.get("message_id"),
                "chat_id": chat.get("id"),
                "sender_id": sender.get("id"),
                "sender_username": sender.get("username"),
            }
        }

        # Handle inbound approvals for messaging tasks
        approval_match = re.search(
            r"^(?:/)?approve\s+([\w\-]+)", text.strip(), re.IGNORECASE
        )
        if approval_match:
            task_id = approval_match.group(1)
            from agents.executors.messaging import MESSAGING_TASKS_DIR

            sentinel_dir = MESSAGING_TASKS_DIR / task_id
            if sentinel_dir.exists():
                if _is_authorized(sender.get("id")):
                    (sentinel_dir / "approved").touch()
                    text = f"Approved messaging task: {task_id}"
                    approvals += 1
                else:
                    text = f"Unauthorized approval attempt for task: {task_id} (id={sender.get('id')})"

        event = queue_event(text, metadata=metadata)
        events.append(event)

    # Save offset
    if max_update_id is not None:
        write_json(POLLING_STATE_PATH, {"last_offset": max_update_id})

    return {
        "polled": len(updates),
        "enqueued": len(events),
        "ignored": ignored,
        "approvals": approvals,
        "new_offset": max_update_id,
        "events": [e.to_dict() for e in events],
    }


def _replace_or_append_loop(
    open_loops: List[OpenLoop], updated: OpenLoop
) -> List[OpenLoop]:
    replaced = False
    next_loops: List[OpenLoop] = []
    for loop in open_loops:
        if loop.id == updated.id:
            next_loops.append(updated)
            replaced = True
        else:
            next_loops.append(loop)
    if not replaced:
        next_loops.append(updated)
    return next_loops


def _active_loop_candidates(open_loops: List[OpenLoop]) -> List[OpenLoop]:
    return cast(List[OpenLoop], rank_open_loops(open_loops))


def _execute_event_action(action, event: Event):
    if not _executor_enabled(action.executor):
        raise ValueError(f"{action.executor} executor is disabled in config")
    if action.executor == "code":
        return execute_code_for_event(action, event, workspace_root=WORKSPACE_ROOT)
    if action.executor == "browser":
        return execute_browser_for_event(action, event)
    if action.executor == "messaging":
        return execute_message_for_event(action, event)
    return execute_research_for_event(action, event)


def _execute_loop_action(action, loop: OpenLoop):
    if not _executor_enabled(action.executor):
        raise ValueError(f"{action.executor} executor is disabled in config")
    if action.executor == "code":
        return execute_code_for_loop(action, loop, workspace_root=WORKSPACE_ROOT)
    if action.executor == "browser":
        return execute_browser_for_loop(action, loop)
    if action.executor == "messaging":
        return execute_message_for_loop(action, loop)
    return execute_research_for_loop(action, loop)


def process_once() -> Dict[str, Any]:
    global _circuit_open, _consecutive_errors

    # Circuit breaker: return early if open
    if _circuit_open:
        payload: Dict[str, Any] = {
            "processed_event": None,
            "processed_loop": None,
            "state": None,
            "actions": [],
            "result": None,
            "error": "CIRCUIT BREAKER TRIPPED — loop halted",
        }
        write_json(
            RUNS_DIR
            / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
            payload,
        )
        write_json(RUNS_DIR / "last_run.json", payload)
        return payload

    ensure_dirs()
    bootstrap_runtime_state()

    queued_events = load_event_queue()
    open_loops = load_open_loops()
    previous_state = load_current_state()
    state = condense_state(queued_events, open_loops, previous_state)
    actions = plan_next_actions(queued_events, open_loops)
    result = None
    processed_event = None
    processed_loop = None
    execution_error = None

    if actions:
        action = actions[0]
        state.current_actions = [action.id]

        try:
            if queued_events:
                # Keep event in queue until after successful execution AND verification
                event_to_process = queued_events[0]
                summary, evidence, artifacts, loop = _execute_event_action(
                    action, event_to_process
                )
                open_loops = _replace_or_append_loop(open_loops, loop)
                result = verify_result(action, summary, evidence, artifacts)
                # Only remove from queue after successful execution and verification
                if result and result.verified:
                    processed_event = queued_events.pop(0)
                else:
                    # Leave event in queue but mark it - verification failed or partial
                    processed_event = event_to_process
            else:
                candidates = _active_loop_candidates(open_loops)
                if candidates:
                    # Use most urgent loop (index 0), matching plan_next_actions() which
                    # selects ranked_loops[0] (most urgent) via _action_for_loop()
                    processed_loop = candidates[0]
                    summary, evidence, artifacts, updated_loop = _execute_loop_action(
                        action, processed_loop
                    )
                    open_loops = _replace_or_append_loop(open_loops, updated_loop)
                    result = verify_result(action, summary, evidence, artifacts)

            if result:
                state.last_verified_result = result.to_dict()

            # Only fully verified work resets the circuit breaker.
            if result is None or result.verified:
                _reset_circuit()
        except Exception as e:
            execution_error = str(e)
            _consecutive_errors += 1
            if _consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                _trip_circuit()
                execution_error = f"CIRCUIT BREAKER TRIPPED after {MAX_CONSECUTIVE_ERRORS} consecutive errors: {execution_error}"
    else:
        # Idle cycle — prune stale loops
        state.current_actions = []
        open_loops = prune_old_loops(open_loops)

    state = condense_state(queued_events, open_loops, state)
    save_event_queue(queued_events)
    save_open_loops(open_loops)
    write_json(CURRENT_STATE_PATH, state.to_dict())
    _persist_circuit_breaker_state()

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "processed_event": processed_event.to_dict() if processed_event else None,
        "processed_loop": processed_loop.to_dict() if processed_loop else None,
        "state": state.to_dict(),
        "actions": [action.to_dict() for action in actions],
        "result": result.to_dict() if result else None,
        "error": execution_error,
        "circuit_open": _circuit_open,
    }
    write_json(RUNS_DIR / f"run-{run_stamp}.json", payload)
    write_json(RUNS_DIR / "last_run.json", payload)
    return payload


# Load persisted circuit breaker state on startup
_load_circuit_breaker_state()


if __name__ == "__main__":
    ensure_dirs()
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        created = bootstrap_runtime_state()
        print(json.dumps({"bootstrapped": created}, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "enqueue":
        bootstrap_runtime_state()
        text = " ".join(sys.argv[2:]).strip() or "Queued event"
        event = queue_event(text)
        print(json.dumps({"queued": event.to_dict()}, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "poll":
        bootstrap_runtime_state()
        summary = poll_events()
        summary["offset_stored_at"] = str(POLLING_STATE_PATH.relative_to(store.BASE))
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(process_once(), indent=2))
