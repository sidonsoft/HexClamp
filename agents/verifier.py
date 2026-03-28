from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

import yaml

from agents.models import Action, Result
from agents.store import STATE_DIR, read_json, write_json
from agents.validate import validate_payload
from agents.executors.base import _load_policies  # Import from single source of truth


MIN_EVIDENCE_BY_TYPE = {
    "research": 1,
    "code": 2,
    "browser": 2,
    "messaging": 1,
}

VERIFIER_LEARNING_THRESHOLD = 2

CHECK_PREFIXES = (
    "agent:",
    "git:",
    "quality_gate:",
    "syntax:",
    "py_compile:",
)


def _default_learning_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "total_checks": 0,
        "false_positives": 0,
        "types": {},
        "learned_requirements": {},
        "recent_misses": [],
    }


def _verifier_learning_path() -> Path:
    return STATE_DIR / "verifier_learning.json"


def _load_learning_state() -> dict[str, Any]:
    data = read_json(_verifier_learning_path(), default=None)
    if not isinstance(data, dict):
        return _default_learning_state()
    default = _default_learning_state()
    default.update(data)
    default.setdefault("types", {})
    default.setdefault("learned_requirements", {})
    default.setdefault("recent_misses", [])
    return default


def _save_learning_state(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(_verifier_learning_path(), state)


def _is_metadata_evidence(item: str) -> bool:
    return any(item.startswith(prefix) for prefix in CHECK_PREFIXES)


def _evidence_file_exists(item: str) -> bool:
    """
    Check if an evidence item exists as a file.
    Handles both absolute paths and workspace-relative paths.
    """
    item = item.strip()
    if not item:
        return False

    # Skip non-file evidence markers (agent IDs, git status, quality gate markers)
    if _is_metadata_evidence(item):
        return True  # These are metadata, count as valid evidence

    # Issue #10: Task metadata files (pending execution records) don't count as completion evidence
    # Skip browser/messaging task files - they indicate queued work, not completed work
    task_meta_prefixes = (
        "runs/browser_tasks/",
        "runs/messaging_tasks/",
        "runs/code_tasks/",
    )
    if any(item.startswith(prefix) for prefix in task_meta_prefixes):
        # These are task metadata directories - check if it's a completion record
        # Only count it as evidence if it shows actual completion (not just "pending")
        path = Path(item)
        if not path.is_absolute():
            from agents.store import BASE

            path = BASE / path
        if path.exists() and path.suffix == ".json":
            try:
                import json

                data = json.loads(path.read_text(encoding="utf-8"))
                status = data.get("status", "")
                # Only count as evidence if status indicates actual completion
                completion_statuses = (
                    "completed",
                    "success",
                    "sent",
                    "delivered",
                    "verified",
                )
                if any(s in status.lower() for s in completion_statuses):
                    return True
                # Pending/queued status does NOT count as valid completion evidence
                return False
            except (json.JSONDecodeError, OSError):
                return False
        return False

    path = Path(item)
    if path.is_absolute():
        return False

    def _exists_within(base: Path) -> bool:
        candidate = (base / path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return False
        return candidate.exists()

    # Try workspace-relative
    from agents.store import get_workspace_root

    workspace = get_workspace_root()
    if _exists_within(workspace):
        return True

    # Try BASE-relative
    from agents.store import BASE

    if _exists_within(BASE):
        return True

    return False


def verify_result(
    action: Action,
    summary: str,
    evidence: List[str] | None = None,
    artifacts: List[str] | None = None,
) -> Result:
    evidence = evidence or []
    artifacts = artifacts or []

    def _is_valid_evidence(item: str) -> bool:
        if not item:
            return False
        if _is_metadata_evidence(item):
            return True
        return _evidence_file_exists(item)

    valid_evidence = [e for e in evidence if _is_valid_evidence(e)]
    minimum = MIN_EVIDENCE_BY_TYPE.get(action.type, 1)
    count_ok = len(valid_evidence) >= minimum

    # Check policies.yaml — if action type is in required_for, evidence files must exist
    policies = _load_policies()
    required_for = policies.get("verification", {}).get("required_for", [])
    type_requires_verification = action.type in required_for

    # If type requires verification, missing evidence files = not verified
    if type_requires_verification:
        # Count how many evidence items are actually missing files
        missing_files = [
            e
            for e in evidence
            if not _is_valid_evidence(e)
            and not _is_metadata_evidence(e)
        ]
        if missing_files:
            count_ok = False

    contract_passed = _check_preexecution_contract(action)
    checklist_passed = _build_checklist_verdict(action, evidence, artifacts)
    verified = count_ok and contract_passed["passed"] and checklist_passed["passed"]

    result = Result(
        action_id=action.id,
        status="success" if verified else "partial",
        summary=summary,
        evidence=evidence,
        artifacts=artifacts,
        follow_up=(
            []
            if verified
        else _build_follow_up(
            action.type,
            minimum,
            len(valid_evidence),
            contract_passed["missing"] + checklist_passed["missing"],
        )
        ),
        verified=verified,
    )
    validate_payload(result.to_dict(), "result.schema.json")
    _record_verification_learning(action, evidence, artifacts, result)
    return result


def _build_checklist_verdict(
    action: Action, evidence: list[str], artifacts: list[str]
) -> dict[str, list[str] | bool]:
    missing: list[str] = []
    evidence_text = " ".join(evidence).lower()
    learned_requirements = _learned_requirements_for(action.type)

    if action.type == "research":
        if not evidence_text:
            missing.append("claims grounded in evidence")
        if not any(marker in evidence_text for marker in ("source", "cite", "line")):
            missing.append("sources cited when available")
        if "speculation" not in evidence_text and "unsupported" not in evidence_text:
            missing.append("no unsupported speculation")
    elif action.type == "code":
        if not any(
            marker in evidence_text for marker in ("agent:", "syntax:", "py_compile:")
        ):
            missing.append("execution artifacts exist")
        if not any(marker in evidence_text for marker in ("git:modified", "changed")):
            missing.append("changed files are present")
        if not any(marker in evidence_text for marker in ("syntax:", "test", "verify")):
            missing.append("verification signals include tests or syntax checks")
    elif action.type == "browser":
        if not any(Path(item).suffix == ".png" for item in artifacts):
            missing.append("screenshot artifact exists")
        if not any(Path(item).suffix == ".txt" for item in artifacts):
            missing.append("page content artifact exists")
        if not any(token in evidence_text for token in ("http://", "https://", "url:")):
            missing.append("navigation target is recorded")
    elif action.type == "messaging":
        if not any(
            marker in evidence_text
            for marker in ("recipient", "@", "chat_id", "target_recipient")
        ):
            missing.append("recipient is identified")
        if not evidence_text and not artifacts:
            missing.append("message content is recorded")
        if not any(
            token in evidence_text
            for token in ("approved", "sent", "delivered", "delivery")
        ):
            missing.append("approval or delivery evidence exists when required")
    else:
        if not evidence_text:
            missing.append("claims grounded in evidence")

    for requirement in learned_requirements:
        if requirement and requirement not in evidence_text:
            missing.append(f"learned requirement: {requirement}")

    return {"passed": not missing, "missing": missing}


def _check_preexecution_contract(action: Action) -> dict[str, list[str] | bool]:
    missing: list[str] = []
    clauses = [part.strip() for part in action.success_criteria.split(";") if part.strip()]
    lower = action.success_criteria.lower()

    if len(clauses) < 2:
        missing.append("pre-execution contract contains multiple concrete clauses")
    if not any(token in lower for token in ("evidence", "tests", "verification", "artifact", "status")):
        missing.append("pre-execution contract names evidence or verification")
    if action.type in {"code", "browser", "messaging"} and not any(
        token in lower for token in ("command", "pytest", "ruff", "screenshot", "recipient", "approval")
    ):
        missing.append("pre-execution contract includes executor-specific checks")

    return {"passed": not missing, "missing": missing}


def _build_follow_up(
    action_type: str, minimum: int, valid_count: int, checklist_missing: list[str]
) -> list[str]:
    follow_up = [f"Need at least {minimum} valid evidence item(s) for {action_type}"]
    if valid_count < minimum:
        follow_up.append(f"Only {valid_count} valid evidence item(s) were accepted")
    follow_up.extend(f"Missing checklist item: {item}" for item in checklist_missing)
    return follow_up


def _learning_key(action_type: str, requirement: str) -> str:
    return f"{action_type}:{requirement}"


def _learned_requirements_for(action_type: str) -> list[str]:
    state = _load_learning_state()
    learned = state.get("learned_requirements", {})
    if not isinstance(learned, dict):
        return []
    requirements: list[str] = []
    for key, count in learned.items():
        if not (
            key.startswith(f"{action_type}:")
            and isinstance(count, int)
            and count >= VERIFIER_LEARNING_THRESHOLD
        ):
            continue
        requirements.append(key.split(":", 1)[1])
    return requirements


def _record_verification_learning(
    action: Action, evidence: list[str], artifacts: list[str], result: Result
) -> None:
    state = _load_learning_state()
    state["total_checks"] = int(state.get("total_checks", 0)) + 1
    if not result.verified:
        state["false_positives"] = int(state.get("false_positives", 0)) + 1

    types = state.setdefault("types", {})
    action_state = types.setdefault(
        action.type,
        {"checks": 0, "failures": 0, "misses": {}},
    )
    action_state["checks"] = int(action_state.get("checks", 0)) + 1
    if not result.verified:
        action_state["failures"] = int(action_state.get("failures", 0)) + 1

    misses = action_state.setdefault("misses", {})
    for item in result.follow_up:
        if not item.startswith("Missing checklist item: "):
            continue
        requirement = item.removeprefix("Missing checklist item: ").strip()
        if not requirement:
            continue
        misses[requirement] = int(misses.get(requirement, 0)) + 1

        learned_requirements = state.setdefault("learned_requirements", {})
        key = _learning_key(action.type, requirement)
        learned_requirements[key] = int(learned_requirements.get(key, 0)) + 1

    recent = state.setdefault("recent_misses", [])
    recent.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action.type,
            "action_id": action.id,
            "verified": result.verified,
            "follow_up": result.follow_up,
            "evidence_count": len(evidence),
            "artifact_count": len(artifacts),
        }
    )
    state["recent_misses"] = recent[-20:]
    _save_learning_state(state)
