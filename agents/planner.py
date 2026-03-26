from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from agents.store import _parse_datetime
from agents.models import Action, Event, OpenLoop
from agents.validate import validate_payload


PRIORITY_ORDER = ["critical", "high", "normal", "low"]
STATUS_ORDER = ["open", "blocked"]  # open comes first
EXECUTOR_WEIGHTS = {
    "code": 3,  # Code tasks often block other work
    "browser": 2,  # Browser tasks may have dependencies
    "messaging": 2,  # Messaging has external impact
    "research": 1,  # Research is lower priority
}
STALE_THRESHOLD_HOURS = 24  # Consider loops stale after 24 hours without update


def _calculate_loop_age(loop: OpenLoop) -> float:
    """Calculate loop age in hours since creation. Returns 0 on parse error."""
    try:
        created = _parse_datetime(loop.created_at)
    except ValueError:
        return 0.0  # Treat as brand new on parse error
    now = datetime.now(timezone.utc)
    hours_since = (now - created).total_seconds() / 3600
    return hours_since


def _calculate_time_since_update(loop: OpenLoop) -> float:
    """Calculate hours since last update. Returns STALE_THRESHOLD_HOURS+1 on parse error."""
    try:
        updated = _parse_datetime(loop.updated_at)
    except ValueError:
        return float(STALE_THRESHOLD_HOURS) + 1  # Treat as stale on parse error
    now = datetime.now(timezone.utc)
    hours_since = (now - updated).total_seconds() / 3600
    return hours_since


def _is_stale(loop: OpenLoop) -> bool:
    """Check if loop is stale (no updates for threshold period)."""
    return _calculate_time_since_update(loop) > STALE_THRESHOLD_HOURS


def _calculate_escalation_score(loop: OpenLoop) -> int:
    """Calculate escalation score based on evidence count and age."""
    evidence_count = len(loop.evidence)
    age_hours = _calculate_loop_age(loop)

    # More evidence + older age = higher escalation
    # Cap at 100 to prevent extreme values
    return min(int(evidence_count * 10 + age_hours / 2), 100)


def _calculate_urgency_score(loop: OpenLoop) -> tuple[int, int, int, int, int, int]:
    """
    Calculate comprehensive urgency score for ranking.
    Returns a tuple that can be used for sorting (lower = higher priority).

    Ranking factors (in order of importance):
    1. Priority (critical > high > normal > low)
    2. Status (open > blocked)
    3. Executor weight (code > browser/messaging > research)
    4. Blocker count (fewer is better)
    5. Evidence count (more evidence = closer to resolution)
    6. Age (older loops get slight boost)
    7. Staleness (stale loops need attention)
    """
    # Priority score (0-3, lower is better)
    try:
        priority_score = PRIORITY_ORDER.index(loop.priority)
    except ValueError:
        priority_score = 1  # default to normal

    # Status score (0-1, lower is better)
    try:
        status_score = STATUS_ORDER.index(loop.status)
    except ValueError:
        status_score = 1  # blocked

    # Executor weight (inverted, higher weight = lower score)
    executor_weight = EXECUTOR_WEIGHTS.get(loop.owner, 1)
    executor_score = 4 - executor_weight  # invert so 3 -> 0, 1 -> 3

    # Blocker count (direct)
    blocker_count = len(loop.blocked_by)

    # Evidence score (inverted, more evidence = lower score = higher priority)
    # Cap at 10 to prevent extreme values
    evidence_score = -min(len(loop.evidence), 10)

    # Age score (slight boost for older loops)
    age_hours = _calculate_loop_age(loop)
    age_score = -min(int(age_hours / 24), 5)  # -1 per day, cap at -5

    # Staleness score (stale loops get priority boost)
    stale_score = -5 if _is_stale(loop) else 0

    return (
        priority_score,
        status_score,
        executor_score,
        blocker_count,
        evidence_score,
        age_score + stale_score,  # Combine age and staleness
    )


def rank_open_loops(open_loops: List[OpenLoop]) -> List[OpenLoop]:
    """
    Rank open loops by urgency and priority.

    Returns loops sorted by urgency (most urgent first).
    """
    # Filter to only actionable loops
    actionable = [loop for loop in open_loops if loop.status in STATUS_ORDER]

    # Sort by urgency score (lower tuple = higher priority)
    return sorted(actionable, key=_calculate_urgency_score)


def get_loop_summary(loop: OpenLoop) -> dict:
    """Generate a summary of loop state for debugging/reporting."""
    age_hours = _calculate_loop_age(loop)
    since_update = _calculate_time_since_update(loop)

    return {
        "id": loop.id,
        "title": loop.title[:50] + "..." if len(loop.title) > 50 else loop.title,
        "status": loop.status,
        "priority": loop.priority,
        "owner": loop.owner,
        "age_hours": round(age_hours, 1),
        "hours_since_update": round(since_update, 1),
        "is_stale": _is_stale(loop),
        "blocker_count": len(loop.blocked_by),
        "evidence_count": len(loop.evidence),
        "escalation_score": _calculate_escalation_score(loop),
        "urgency_score": _calculate_urgency_score(loop),
        "next_step": (
            loop.next_step[:60] + "..." if len(loop.next_step) > 60 else loop.next_step
        ),
    }


def _build_action(
    action_type: str,
    goal: str,
    inputs: list[str],
    executor: str,
    success_criteria: str,
    risk: str = "low",
) -> Action:
    action = Action(
        id=f"act-{uuid4()}",
        type=action_type,
        goal=goal,
        inputs=inputs,
        executor=executor,
        success_criteria=success_criteria,
        risk=risk,
        status="pending",
    )
    validate_payload(action.to_dict(), "action.schema.json")
    return action


def _loop_contract(loop: OpenLoop) -> tuple[list[str], list[str]]:
    """Derive a pre-execution contract from the loop's current shape."""
    title = loop.title.strip() or "open loop"
    criteria = [
        f"Produce evidence that advances: {title}",
        f"Reflect the loop owner '{loop.owner}' in the work output",
        "Include a concrete next step or a terminal status",
    ]
    verification_commands = [
        "python3 -m agents.loop status",
    ]
    if loop.owner == "code":
        criteria.extend(
            [
                "Show changed files or explicit failure evidence",
                "Include tests, syntax checks, or a quality gate result",
            ]
        )
        verification_commands.extend(
            [
                "python3 -m pytest -q",
                "python3 -m ruff check .",
            ]
        )
    elif loop.owner == "browser":
        criteria.extend(
            [
                "Capture screenshot evidence and page content",
                "Record the navigation target or page URL",
            ]
        )
        verification_commands.append("python3 -m pytest -q tests/test_browser_executor.py")
    elif loop.owner == "messaging":
        criteria.extend(
            [
                "Identify the recipient and delivery intent",
                "Record approval or delivery evidence when required",
            ]
        )
        verification_commands.append("python3 -m pytest -q tests/test_messaging_delivery.py")
    elif loop.owner == "research":
        criteria.extend(
            [
                "Ground claims in local file evidence",
                "Cite sources or file references when available",
            ]
        )
        verification_commands.append("python3 -m pytest -q tests/test_planner.py")
    return criteria, verification_commands


def classify_text(text: str) -> str:
    normalized = text.lower()

    # System/admin control messages (highest priority — check first)
    system_patterns = [
        "reload",
        "restart",
        "reset",
        "shutdown",
        "kill",
        "abort",
        "pause loop",
        "halt",
        "emergency",
        "circuit breaker",
        "bootstrap",
        "init",
        "reinitialize",
        "flush",
        "clear cache",
        "set mode",
        "set state",
        "update config",
        "change policy",
    ]
    if any(token in normalized for token in system_patterns):
        return "system"

    # Specific filename / extension patterns (very strong code signal)
    # Check for .py extension or specific file references
    if (
        ".py" in text
        or any(ext in text for ext in [".yaml", ".json", ".sh", ".md"])
        and any(
            kw in normalized
            for kw in [
                "edit",
                "modify",
                "fix",
                "create",
                "update",
                "add",
                "remove",
                "refactor",
                "implement",
            ]
        )
    ):
        return "code"

    # Longer/specific code patterns first (most specific → least specific)
    code_specific = [
        "create function",
        "create a function",
        "define function",
        "write a function",
        "implement",
        "write code",
        "fix bug",
        "bug fix",
        "refactor",
        "create class",
        "define class",
        "write script",
        "python script",
        "add to",
        "modify",
        "update file",
        "edit file",
    ]
    if any(phrase in normalized for phrase in code_specific):
        return "code"

    # Shorter code keywords (only if no other category matched)
    code_keywords = ["def ", "class ", "import ", "from ", "async ", "await "]
    if any(token in normalized for token in code_keywords):
        return "code"

    # Browser patterns
    browser_patterns = [
        "browser",
        "click",
        "page",
        "site",
        "login",
        "navigate",
        "web",
        "url",
        "screenshot",
        "scroll",
        "hover",
        "submit form",
    ]
    if any(token in normalized for token in browser_patterns):
        return "browser"

    # Messaging patterns
    messaging_patterns = [
        "send message",
        "send a message",
        "reply to",
        "telegram message",
        "email user",
        "send email",
        "notify",
        "slack",
        "discord message",
    ]
    if any(token in normalized for token in messaging_patterns):
        return "message"

    return "research"


def _action_for_event(event: Event) -> Action:
    text = event.payload.get("text", "")
    action_type = classify_text(text)

    if action_type == "code":
        return _build_action(
            "code",
            f"Prepare a code execution brief for event {event.id}",
            ["current_state", event.id],
            "code",
            "A concrete code-oriented next step is recorded with evidence",
            risk="medium",
        )
    if action_type == "browser":
        return _build_action(
            "browser",
            f"Prepare a browser execution brief for event {event.id}",
            ["current_state", event.id],
            "browser",
            "A browser-oriented next step is recorded with visible-state evidence",
            risk="medium",
        )
    if action_type == "message":
        return _build_action(
            "message",
            f"Prepare a messaging execution brief for event {event.id}",
            ["current_state", event.id],
            "messaging",
            "A message draft or approval-needed send plan is recorded",
            risk="medium",
        )
    return _build_action(
        "research",
        f"Summarize event {event.id} into a grounded note",
        ["current_state", event.id],
        "research",
        "A concise grounded summary is written to recent_changes.md",
    )


def _action_for_loop(loop: OpenLoop) -> Action:
    action_type = (
        loop.owner
        if loop.owner in {"research", "code", "browser", "messaging"}
        else classify_text(loop.title)
    )

    acceptance_criteria, verification_commands = _loop_contract(loop)
    if action_type == "code":
        return _build_action(
            "code",
            f"Advance code loop: {loop.title}",
            ["current_state", loop.id],
            "code",
            "; ".join(acceptance_criteria + verification_commands),
            risk="medium",
        )
    if action_type == "browser":
        return _build_action(
            "browser",
            f"Advance browser loop: {loop.title}",
            ["current_state", loop.id],
            "browser",
            "; ".join(acceptance_criteria + verification_commands),
            risk="medium",
        )
    if action_type == "messaging":
        return _build_action(
            "message",
            f"Advance messaging loop: {loop.title}",
            ["current_state", loop.id],
            "messaging",
            "; ".join(acceptance_criteria + verification_commands),
            risk="medium",
        )
    return _build_action(
        "research",
        f"Advance research loop: {loop.title}",
        ["current_state", loop.id],
        "research",
        "; ".join(acceptance_criteria + verification_commands),
    )


def plan_next_actions(
    queued_events: List[Event], open_loops: List[OpenLoop]
) -> List[Action]:
    if queued_events:
        return [_action_for_event(queued_events[0])]

    ranked_loops = rank_open_loops(open_loops)
    if ranked_loops:
        return [_action_for_loop(ranked_loops[0])]

    return []
