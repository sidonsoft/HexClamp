from __future__ import annotations

import yaml
from pathlib import Path
from typing import List

from agents.models import Action, Result
from agents.validate import validate_payload


MIN_EVIDENCE_BY_TYPE = {
    "research": 1,
    "code": 2,
    "browser": 2,
    "message": 1,
}

CHECK_PREFIXES = (
    "agent:",
    "git:",
    "quality_gate:",
    "syntax:",
    "py_compile:",
)


def _load_policies() -> dict:
    """Load policies.yaml to check required_for."""
    policies_path = Path(__file__).parent.parent / "config" / "policies.yaml"
    if policies_path.exists():
        with open(policies_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


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
    return result


def _build_checklist_verdict(
    action: Action, evidence: list[str], artifacts: list[str]
) -> dict[str, list[str] | bool]:
    missing: list[str] = []
    evidence_text = " ".join(evidence).lower()

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
    elif action.type == "message":
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
