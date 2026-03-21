from __future__ import annotations

import yaml
from pathlib import Path
from typing import List

from models import Action, Result
from validate import validate_payload


MIN_EVIDENCE_BY_TYPE = {
    "research": 1,
    "code": 2,
    "browser": 2,
    "message": 1,
}


def _load_policies() -> dict:
    """Load policies.yaml to check required_for."""
    policies_path = Path(__file__).parent.parent / "config" / "policies.yaml"
    if policies_path.exists():
        with open(policies_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def _evidence_file_exists(item: str) -> bool:
    """
    Check if an evidence item exists as a file.
    Handles both absolute paths and workspace-relative paths.
    """
    item = item.strip()
    if not item:
        return False

    # Skip non-file evidence markers (agent IDs, git status, quality gate markers)
    skip_prefixes = ("agent:", "git:", "quality_gate:", "syntax:", "py_compile:")
    if any(item.startswith(prefix) for prefix in skip_prefixes):
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
            from store import BASE

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
    workspace = Path.home() / ".openclaw" / "workspace"
    if _exists_within(workspace):
        return True

    # Try BASE-relative
    from store import BASE

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

    # Filter evidence to only items that actually exist as files (for file-based evidence)
    # Non-file metadata evidence (agent:, git:, etc.) always counts
    def _is_valid_evidence(item: str) -> bool:
        if not item:
            return False
        skip_prefixes = ("agent:", "git:", "quality_gate:", "syntax:", "py_compile:")
        if any(item.startswith(p) for p in skip_prefixes):
            return True
        # For path-like items, verify the file exists
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
            and not any(
                e.startswith(p)
                for p in ("agent:", "git:", "quality_gate:", "syntax:", "py_compile:")
            )
        ]
        if missing_files:
            count_ok = False

    verified = count_ok

    result = Result(
        action_id=action.id,
        status="success" if verified else "partial",
        summary=summary,
        evidence=evidence,
        artifacts=artifacts,
        follow_up=(
            []
            if verified
            else [f"Need at least {minimum} valid evidence item(s) for {action.type}"]
        ),
        verified=verified,
    )
    validate_payload(result.to_dict(), "result.schema.json")
    return result
