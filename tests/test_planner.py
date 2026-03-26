import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents.models import Event, OpenLoop
from agents.planner import plan_next_actions, rank_open_loops
from agents.verifier import verify_result


class PlannerTests(unittest.TestCase):
    def _loop(
        self,
        loop_id: str,
        *,
        priority: str,
        status: str = "open",
        owner: str = "research",
        blocked_by=None,
        evidence=None,
        created_hours_ago: int = 1,
        updated_hours_ago: int = 1,
    ):
        now = datetime.now(timezone.utc)
        return OpenLoop(
            id=loop_id,
            title=f"Loop {loop_id}",
            status=status,
            priority=priority,
            owner=owner,
            created_at=(now - timedelta(hours=created_hours_ago)).isoformat(),
            updated_at=(now - timedelta(hours=updated_hours_ago)).isoformat(),
            next_step="Do the thing",
            blocked_by=blocked_by or [],
            evidence=evidence or [],
        )

    def test_rank_open_loops_orders_most_urgent_first(self):
        low = self._loop("loop-low", priority="low", owner="research")
        critical = self._loop("loop-critical", priority="critical", owner="code")
        ranked = rank_open_loops([low, critical])
        self.assertEqual([loop.id for loop in ranked], ["loop-critical", "loop-low"])

    def test_rank_open_loops_prefers_open_over_blocked_when_priority_matches(self):
        blocked = self._loop("loop-blocked", priority="high", status="blocked")
        open_loop = self._loop("loop-open", priority="high", status="open")
        ranked = rank_open_loops([blocked, open_loop])
        self.assertEqual(ranked[0].id, "loop-open")

    def test_plan_next_actions_uses_top_ranked_loop(self):
        low = self._loop("loop-low", priority="low", owner="research")
        critical = self._loop("loop-critical", priority="critical", owner="code")
        actions = plan_next_actions([], [low, critical])
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].executor, "code")
        self.assertIn("loop-critical", actions[0].inputs)

    def test_plan_next_actions_prefers_queued_events_over_open_loops(self):
        event = Event(
            id="evt-1",
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="chat",
            kind="request",
            payload={"text": "send telegram message to @sidonsoft: hello"},
            tags=["user"],
            priority="normal",
        )
        loop = self._loop("loop-critical", priority="critical", owner="code")
        actions = plan_next_actions([event], [loop])
        self.assertEqual(actions[0].executor, "messaging")
        self.assertIn("evt-1", actions[0].goal)

    def test_plan_next_actions_embeds_pre_execution_contract(self):
        loop = self._loop("loop-code", priority="high", owner="code")
        actions = plan_next_actions([], [loop])
        self.assertGreaterEqual(len(actions[0].success_criteria.split(";")), 2)
        self.assertIn("evidence", actions[0].success_criteria.lower())
        self.assertIn("pytest", actions[0].success_criteria.lower())

    def test_verifier_requires_contract_clarity_for_execution_actions(self):
        loop = self._loop("loop-code", priority="high", owner="code")
        action = plan_next_actions([], [loop])[0]
        result = verify_result(
            action,
            "summary",
            evidence=["agent:ok", "git:modified:file.py", "syntax:ok"],
        )
        self.assertTrue(result.verified)

    def test_verifier_rejects_vague_contracts(self):
        from agents.models import Action

        action = Action(
            id="act-1",
            type="code",
            goal="test",
            inputs=[],
            executor="code",
            success_criteria="Do the thing",
            risk="medium",
            status="pending",
        )
        result = verify_result(
            action,
            "summary",
            evidence=["agent:ok", "git:modified:file.py", "syntax:ok"],
        )
        self.assertFalse(result.verified)


if __name__ == "__main__":
    unittest.main()
