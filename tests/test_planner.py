import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents.models import Event, OpenLoop
from agents.planner import plan_next_actions, rank_open_loops


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


if __name__ == "__main__":
    unittest.main()
