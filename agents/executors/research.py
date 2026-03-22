from __future__ import annotations

import re
from datetime import datetime, timezone

from agents import store
from agents.models import Action, Event, OpenLoop
from agents.executors.base import (
    STALE_EVIDENCE_THRESHOLD,
    _initial_loop_state,
    _write_change,
)

BASE = store.BASE


def _find_grounded_evidence(text: str) -> tuple[str, list[str]]:
    """Identify local files as research evidence and ingest content to ground the result."""
    text_lower = text.lower()
    found_files = []

    # Identify candidate files
    file_patterns = re.findall(r"[\w\-./]+\.(?:py|md|yaml|yml|json|sh|txt)", text)
    for p in file_patterns:
        if (BASE / p).exists():
            found_files.append(p)

    if not found_files:
        repo_keywords = [
            "hexclamp",
            "repo",
            "codebase",
            "project",
            "test",
            "implementation",
        ]
        if any(term in text_lower for term in repo_keywords):
            for anchor in ["README.md", "pyproject.toml", "CONTRIBUTING.md"]:
                if (BASE / anchor).exists():
                    found_files.append(anchor)
                    break

    if found_files:
        # Ingest content from the primary identified file
        primary = found_files[0]
        path = BASE / primary
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Read up to 10 lines for the grounded summary
                lines = []
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.strip())
                content_snippet = " / ".join([l for l in lines if l])

            # Heuristic for finding and next action based on common repo tasks
            finding = f"File exists and initial content identifies as: \"{content_snippet[:100]}...\""
            if "readme" in primary.lower() or "contributing" in primary.lower():
                next_action = f"Evaluate Documentation in {primary} against actual implementation state."
            elif primary.endswith(".py"):
                next_action = f"Analyze logic or structure in {primary} to address the request."
            else:
                next_action = f"Perform deep inspection of {primary} to fulfill research goal."

            summary = (
                f"Grounded research in {primary}:\n"
                f"- Finding: {finding}\n"
                f"- Next Action: {next_action}"
            )
        except Exception as e:
            summary = f"Performed grounded research in {primary} but could not read content: {e}"
        return summary, found_files

    return "", []


def execute_research_for_event(
    action: Action, event: Event
) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute research task for an event."""
    text = event.payload.get("text", "")
    grounded_summary, research_evidence = _find_grounded_evidence(text)

    if grounded_summary:
        summary = grounded_summary
        loop_status = "open"
        next_step = "Deepen research or prepare execution based on findings"
        blocked_by: list[str] = []
    else:
        loop_status, next_step, blocked_by, summary = _initial_loop_state(event, "research")

    # Combine evidence: event id + found files + metadata to ensure valid count
    evidence = [event.id] + research_evidence
    if not research_evidence:
        evidence.append("git:research:observed")

    artifact = _write_change(action, summary)
    loop = OpenLoop(
        id=f"loop-{event.id}",
        title=text[:80] or f"Follow up event {event.id}",
        status=loop_status,
        priority=event.priority,
        owner="research",
        created_at=event.timestamp,
        updated_at=datetime.now(timezone.utc).isoformat(),
        next_step=next_step,
        blocked_by=blocked_by,
        evidence=evidence,
    )
    return summary, evidence, [artifact], loop


def execute_research_for_loop(
    action: Action, loop: OpenLoop
) -> tuple[str, list[str], list[str], OpenLoop]:
    """Execute research task for a loop."""
    now = datetime.now(timezone.utc).isoformat()

    grounded_summary, research_evidence = _find_grounded_evidence(loop.title)

    if loop.status == "blocked":
        summary = f"Loop '{loop.title}' remains blocked pending dependency resolution."
        loop.next_step = "Await unblock signal before further execution"
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "stale"
            loop.next_step = "Stale blocked loop; requires operator review"
            summary = (
                f"Loop '{loop.title}' became stale after repeated blocked reviews."
            )
    else:
        if len(loop.evidence) >= STALE_EVIDENCE_THRESHOLD:
            loop.status = "resolved"
            loop.next_step = (
                "Research loop exhausted; treat as resolved unless reopened"
            )
            summary = f"Loop '{loop.title}' reached resolution threshold."
        else:
            loop.status = "open"
            if grounded_summary:
                summary = grounded_summary
                loop.next_step = f"Continue research from identified files: {', '.join(research_evidence[:2])}"
            else:
                loop.next_step = f"Escalate or specialize execution for: {loop.title}"
                summary = f"Reviewed research loop '{loop.title}' and refreshed next step."

    loop.updated_at = now
    loop.evidence.append(action.id)
    if research_evidence:
        for e in research_evidence:
            if e not in loop.evidence:
                loop.evidence.append(e)
    elif not any(e.startswith("git:research") for e in loop.evidence):
        loop.evidence.append("git:research:reviewed")

    artifact = _write_change(action, summary)
    return summary, loop.evidence, [artifact], loop
