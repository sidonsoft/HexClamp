import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

from executors import _parse_message_task


class MessageParserTests(unittest.TestCase):
    def test_recipient_regression_does_not_parse_literal_to(self):
        task = _parse_message_task(
            "send telegram message to @sidonsoft: test message from hexclamp"
        )
        self.assertEqual(task["channel"], "telegram")
        self.assertEqual(task["recipient"], "@sidonsoft")
        self.assertEqual(task["content"], "test message from hexclamp")
        self.assertNotEqual(task["recipient"], "to")

    def test_plain_recipient_without_handle(self):
        task = _parse_message_task("send signal message to russell: hello there")
        self.assertEqual(task["channel"], "signal")
        self.assertEqual(task["recipient"], "russell")
        self.assertEqual(task["content"], "hello there")

    def test_urgent_message_skips_approval(self):
        task = _parse_message_task(
            "urgent: send telegram message to @sidonsoft: ping now"
        )
        self.assertFalse(task["requires_approval"])


if __name__ == "__main__":
    unittest.main()
