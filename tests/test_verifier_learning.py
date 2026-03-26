import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents.models import Action
from agents import verifier


class VerifierLearningTests(unittest.TestCase):
    def _action(self) -> Action:
        return Action(
            id="act-code-1",
            type="code",
            goal="Validate code change",
            inputs=[],
            executor="code",
            success_criteria="Run pytest; capture evidence; capture syntax output",
            risk="medium",
            status="pending",
        )

    def test_verifier_learns_repeated_missing_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "state"
            state_dir.mkdir(parents=True)

            with patch.object(verifier, "STATE_DIR", state_dir):
                action = self._action()
                first = verifier.verify_result(
                    action,
                    "summary",
                    evidence=["agent:ok", "git:modified:file.py"],
                )
                second = verifier.verify_result(
                    action,
                    "summary",
                    evidence=["agent:ok", "git:modified:file.py"],
                )
                third = verifier.verify_result(
                    action,
                    "summary",
                    evidence=["agent:ok", "git:modified:file.py"],
                )

            learning = json.loads((state_dir / "verifier_learning.json").read_text())
            learned = learning["learned_requirements"]["code:verification signals include tests or syntax checks"]

            self.assertFalse(first.verified)
            self.assertFalse(second.verified)
            self.assertFalse(third.verified)
            self.assertEqual(learned, 3)
            self.assertIn(
                "Missing checklist item: learned requirement: verification signals include tests or syntax checks",
                third.follow_up,
            )


if __name__ == "__main__":
    unittest.main()
