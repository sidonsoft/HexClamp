from __future__ import annotations

from typing import List

from models import Action, Result
from validate import validate_payload


MIN_EVIDENCE_BY_TYPE = {
    "research": 1,
    "code": 2,
    "browser": 2,
    "message": 1,
}


def verify_result(action: Action, summary: str, evidence: List[str] | None = None, artifacts: List[str] | None = None) -> Result:
    evidence = evidence or []
    artifacts = artifacts or []
    minimum = MIN_EVIDENCE_BY_TYPE.get(action.type, 1)
    verified = len(evidence) >= minimum

    result = Result(
        action_id=action.id,
        status="success" if verified else "partial",
        summary=summary,
        evidence=evidence,
        artifacts=artifacts,
        follow_up=[] if verified else [f"Need at least {minimum} evidence item(s) for {action.type}"],
        verified=verified,
    )
    validate_payload(result.to_dict(), "result.schema.json")
    return result
