import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "agents"))

from agents.delivery import TelegramDeliveryAgent, DeliveryResult


class TestTelegramDeliveryAgent(unittest.TestCase):
    """Tests for TelegramDeliveryAgent."""

    def setUp(self):
        self.env_patcher = patch.dict(
            "os.environ", {"TELEGRAM_BOT_TOKEN": "fakeproto:faketoken"}
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_send_success_returns_message_id(self):
        """Test that a successful send returns the message_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123},
        }

        with patch("agents.delivery.requests.post", return_value=mock_response):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="123456789", content="Hello world")

        self.assertTrue(result.success)
        self.assertEqual(result.message_id, 123)
        self.assertIsNone(result.error)
        self.assertEqual(result.recipient, "123456789")

    def test_send_failure_returns_error_403(self):
        """Test that 403 Forbidden returns appropriate error."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "ok": False,
            "description": "Forbidden: bot cannot send messages to users",
        }

        with patch("agents.delivery.requests.post", return_value=mock_response):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="123456789", content="Hello world")

        self.assertFalse(result.success)
        self.assertIsNone(result.message_id)
        self.assertIn("403", result.error)
        self.assertIn("Forbidden", result.error)

    def test_send_failure_returns_error_429_rate_limit(self):
        """Test that 429 Too Many Requests returns rate limit error."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "ok": False,
            "description": "Too Many Requests",
            "parameters": {"retry_after": 30},
        }

        with patch("agents.delivery.requests.post", return_value=mock_response):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="123456789", content="Hello world")

        self.assertFalse(result.success)
        self.assertIsNone(result.message_id)
        self.assertIn("429", result.error)
        self.assertIn("Rate limit", result.error)
        self.assertIn("30", result.error)

    def test_send_failure_returns_error_400_bad_request(self):
        """Test that 400 Bad Request returns appropriate error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }

        with patch("agents.delivery.requests.post", return_value=mock_response):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="invalid_chat", content="Hello world")

        self.assertFalse(result.success)
        self.assertIsNone(result.message_id)
        self.assertIn("400", result.error)

    def test_username_resolution_success(self):
        """Test that @username is resolved to chat_id via getChat."""
        # Mock getChat response
        get_chat_response = MagicMock()
        get_chat_response.json.return_value = {
            "ok": True,
            "result": {"id": 999888777},
        }
        # Mock sendMessage response
        send_response = MagicMock()
        send_response.status_code = 200
        send_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 456},
        }

        with patch("agents.delivery.requests.get", return_value=get_chat_response):
            with patch("agents.delivery.requests.post", return_value=send_response):
                agent = TelegramDeliveryAgent()
                result = agent.send(recipient="@someuser", content="Hello!")

        self.assertTrue(result.success)
        self.assertEqual(result.message_id, 456)
        self.assertEqual(result.recipient, "@someuser")

    def test_username_resolution_failure(self):
        """Test that invalid username returns error without sending."""
        get_chat_response = MagicMock()
        get_chat_response.json.return_value = {
            "ok": False,
            "description": "Chat not found",
        }

        with patch("agents.delivery.requests.get", return_value=get_chat_response):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="@nonexistent", content="Hello!")

        self.assertFalse(result.success)
        self.assertIsNone(result.message_id)
        self.assertIn("Could not resolve username", result.error)
        self.assertEqual(result.recipient, "@nonexistent")

    def test_send_timeout_returns_error(self):
        """Test that request timeout returns appropriate error."""
        import requests

        with patch(
            "agents.delivery.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="123456789", content="Hello world")

        self.assertFalse(result.success)
        self.assertIn("timed out", result.error)

    def test_send_network_error_returns_error(self):
        """Test that network error returns appropriate error."""
        import requests

        with patch(
            "agents.delivery.requests.post",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            agent = TelegramDeliveryAgent()
            result = agent.send(recipient="123456789", content="Hello world")

        self.assertFalse(result.success)
        self.assertIn("Request failed", result.error)


if __name__ == "__main__":
    unittest.main()
