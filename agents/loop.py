from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from pathlib import Path

from condenser import condense_state
from executors import (
    execute_browser_for_event,
    execute_browser_for_loop,
    execute_code_for_event,
    execute_code_for_loop,
    execute_message_for_event,
    execute_message_for_loop,
    execute_research_for_event,
    execute_research_for_loop,
)

WORKSPACE_ROOT = Path.home() / ".openclaw" / "workspace"
from models import CurrentState, Event, OpenLoop
from observer import observe_chat_message
from planner import plan_next_actions, rank_open_loops
from store import RUNS_DIR, STATE_DIR, append_json_array, ensure_dirs, read_json, write_json
from validate import validate_payload
from verifier import verify_result


EVENT_QUEUE_PATH = STATE_DIR / "event_queue.json"
OPEN_LOOPS_PATH = STATE_DIR / "open_loops.json"
CURRENT_STATE_PATH = STATE_DIR / "current_state.json"


def load_current_state() -> CurrentState:
    data = read_json(CURRENT_STATE_PATH)
    if not data:
        return CurrentState(goal="Keep hydra-claw-loop coherent and progressing")
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


def queue_event(text: str, priority: str = "normal") -> Event:
    event = observe_chat_message(text, priority=priority)
    append_json_array(EVENT_QUEUE_PATH, event.to_dict())
    return event


def _replace_or_append_loop(open_loops: List[OpenLoop], updated: OpenLoop) -> List[OpenLoop]:
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
    return rank_open_loops(open_loops)


def _execute_event_action(action, event: Event):
    if action.executor == "code":
        return execute_code_for_event(action, event, workspace_root=WORKSPACE_ROOT)
    if action.executor == "browser":
        return execute_browser_for_event(action, event)
    if action.executor == "messaging":
        return execute_message_for_event(action, event)
    return execute_research_for_event(action, event)


def _execute_loop_action(action, loop: OpenLoop):
    if action.executor == "code":
        return execute_code_for_loop(action, loop, workspace_root=WORKSPACE_ROOT)
    if action.executor == "browser":
        return execute_browser_for_loop(action, loop)
    if action.executor == "messaging":
        return execute_message_for_loop(action, loop)
    return execute_research_for_loop(action, loop)


def process_once() -> Dict[str, Any]:
    ensure_dirs()

    queued_events = load_event_queue()
    open_loops = load_open_loops()
    previous_state = load_current_state()
    state = condense_state(queued_events, open_loops, previous_state)
    actions = plan_next_actions(queued_events, open_loops)
    result = None
    processed_event = None
    processed_loop = None

    if actions:
        action = actions[0]
        state.current_actions = [action.id]

        if queued_events:
            processed_event = queued_events.pop(0)
            summary, evidence, artifacts, loop = _execute_event_action(action, processed_event)
            open_loops = _replace_or_append_loop(open_loops, loop)
            result = verify_result(action, summary, evidence, artifacts)
        else:
            candidates = _active_loop_candidates(open_loops)
            if candidates:
                processed_loop = candidates[-1]
                summary, evidence, artifacts, updated_loop = _execute_loop_action(action, processed_loop)
                open_loops = _replace_or_append_loop(open_loops, updated_loop)
                result = verify_result(action, summary, evidence, artifacts)

        if result:
            state.last_verified_result = result.to_dict()
    else:
        state.current_actions = []

    state = condense_state(queued_events, open_loops, state)
    save_event_queue(queued_events)
    save_open_loops(open_loops)
    write_json(CURRENT_STATE_PATH, state.to_dict())

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "processed_event": processed_event.to_dict() if processed_event else None,
        "processed_loop": processed_loop.to_dict() if processed_loop else None,
        "state": state.to_dict(),
        "actions": [action.to_dict() for action in actions],
        "result": result.to_dict() if result else None,
    }
    write_json(RUNS_DIR / f"run-{run_stamp}.json", payload)
    write_json(RUNS_DIR / "last_run.json", payload)
    return payload


if __name__ == "__main__":
    ensure_dirs()
    if len(sys.argv) > 1 and sys.argv[1] == "enqueue":
        text = " ".join(sys.argv[2:]).strip() or "Queued event"
        event = queue_event(text)
        print(json.dumps({"queued": event.to_dict()}, indent=2))
    else:
        print(json.dumps(process_once(), indent=2))
