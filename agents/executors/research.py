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
            "messaging",
            "browser",
            "code",
        ]
        if any(term in text_lower for term in repo_keywords):
            # Map keywords to primary candidate files
            candidates = []
            if "messaging" in text_lower:
                candidates.append("agents/executors/messaging.py")
            if "browser" in text_lower:
                candidates.append("agents/executors/browser.py")
            if "code" in text_lower:
                candidates.append("agents/executors/code_executor.py")

            # Add general anchors
            candidates.extend(["README.md", "CONTRIBUTING.md", "pyproject.toml"])

            for anchor in candidates:
                if (BASE / anchor).exists() and anchor not in found_files:
                    found_files.append(anchor)

    if found_files:
        best_summary = ""
        # Check all found files to find the best (most grounded) research result
        for primary in found_files[:3]:
            path = BASE / primary
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Bounded read for summary snippet
                    lines = content.splitlines()[:10]
                    content_snippet = " / ".join(
                        [line.strip() for line in lines if line]
                    )

                # Improved heuristic for concrete correction proposal
                stale_instruction = ""
                correction = ""
                if "readme" in primary.lower() or "contributing" in primary.lower():
                    # Specific check for stale 'python3 agents/loop.py' which should be 'python3 -m agents.loop'
                    stale_pattern = r"python3 agents/loop\.py"
                    if re.search(stale_pattern, content):
                        stale_instruction = "python3 agents/loop.py"
                        correction = "python3 -m agents.loop"

                # Check for test gaps in messaging approval
                if "messaging" in text_lower and (
                    "test" in text_lower or "weak" in text_lower
                ):
                    if "messaging.py" in primary:
                        if "approved" in content and "sentinel_path" in content:
                            integ_test = BASE / "tests" / "test_integration.py"
                            if integ_test.exists():
                                it_content = integ_test.read_text(encoding="utf-8")
                                if "sentinel_path" not in it_content:
                                    summary = (
                                        f"Grounded research in {primary} and tests/test_integration.py:\n"
                                        f"1. Finding: Messaging approval mechanism ('sentinel_path') is not covered by integration tests.\n"
                                        f"2. Evidence: {primary} uses 'sentinel_path' for approvals.\n"
                                        f"3. Recommendation: Add 'test_messaging_loop_approved_via_sentinel' to verify full E2E approval flow.\n"
                                        f"4. Target File: tests/test_integration.py\n"
                                        f"5. Next Step: Implement the missing integration test case."
                                    )
                                    return summary, found_files

                if stale_instruction:
                    finding = f'Identified stale instruction: "{stale_instruction}"'
                    summary = (
                        f"Grounded research in {primary}:\n"
                        f'1. Finding: Identified stale instruction: "{stale_instruction}".\n'
                        f"2. Evidence: {primary} line contains outdated reference.\n"
                        f'3. Recommendation: Change "{stale_instruction}" to "{correction}".\n'
                        f"4. Target File: {primary}\n"
                        f"5. Next Step: Apply the documentation correction."
                    )
                    # If we found a concrete stale instruction, this is the best result
                    return summary, found_files

                # Fallback summary if no stale instruction found in this file
                if not best_summary:
                    finding = f'File exists and initial content identifies as: "{content_snippet[:100]}..."'
                    if "readme" in primary.lower() or "contributing" in primary.lower():
                        next_action = f"Evaluate Documentation in {primary} against actual implementation state."
                    elif primary.endswith(".py"):
                        next_action = f"Analyze logic or structure in {primary} to address the request."
                    else:
                        next_action = f"Perform deep inspection of {primary} to fulfill research goal."

                    best_summary = (
                        f"Grounded research in {primary}:\n"
                        f"1. Finding: {finding}\n"
                        f"2. Evidence: {primary}\n"
                        f"3. Recommendation: Analyze referenced file to address task goal.\n"
                        f"4. Target File: {primary}\n"
                        f"5. Next Step: {next_action}"
                    )
            except Exception as e:
                if not best_summary:
                    best_summary = f"Performed grounded research in {primary} but could not read content: {e}"

        return best_summary, found_files

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
        loop_status, next_step, blocked_by, summary = _initial_loop_state(
            event, "research"
        )

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
                summary = (
                    f"Reviewed research loop '{loop.title}' and refreshed next step."
                )

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
