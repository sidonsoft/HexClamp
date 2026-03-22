from __future__ import annotations

import os
import requests
from dataclasses import dataclass
from typing import Any, Optional, cast


def get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    return token


def get_bot_api() -> str:
    return f"https://api.telegram.org/bot{get_bot_token()}"


@dataclass
class DeliveryResult:
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None
    recipient: Optional[str] = None


class TelegramDeliveryAgent:
    def send(
        self, recipient: str, content: str, parse_mode: str = "Markdown"
    ) -> DeliveryResult:
        """
        Send a message via Telegram Bot API.

        Args:
            recipient: username (@xxx) or numeric chat_id
            content: message text
            parse_mode: "Markdown" or "HTML"

        Returns:
            DeliveryResult with success, message_id, error, recipient
        """
        # Resolve username to chat_id if needed
        chat_id: str | int | None = recipient
        if recipient.startswith("@"):
            chat_id = self._resolve_username(recipient)
            if chat_id is None:
                return DeliveryResult(
                    success=False,
                    error=f"Could not resolve username {recipient}",
                    recipient=recipient,
                )

        # Send the message
        assert chat_id is not None
        return self._send_message(
            chat_id, content, parse_mode, original_recipient=recipient
        )

    def _resolve_username(self, username: str) -> Optional[int]:
        """Resolve a Telegram username (@xxx) to a numeric chat_id via getChat API."""
        try:
            response = requests.get(
                f"{get_bot_api()}/getChat",
                params={"chat_id": username},
                timeout=10,
            )
            data = response.json()

            if not data.get("ok"):
                return None

            result = cast(dict[str, Any], data["result"])
            return cast(int, result["id"])
        except requests.exceptions.RequestException:
            return None

    def _send_message(
        self, chat_id: str | int, content: str, parse_mode: str, original_recipient: str
    ) -> DeliveryResult:
        """Send message via sendMessage API."""
        try:
            response = requests.post(
                f"{get_bot_api()}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": content,
                    "parse_mode": parse_mode,
                },
                timeout=15,
            )
            status_code = response.status_code

            if status_code == 403:
                return DeliveryResult(
                    success=False,
                    error="403 Forbidden: Bot cannot send messages to this user (they haven't started a chat with the bot, or have blocked it)",
                    recipient=original_recipient,
                )

            if status_code == 429:
                retry_after = (
                    response.json().get("parameters", {}).get("retry_after", "unknown")
                )
                return DeliveryResult(
                    success=False,
                    error=f"429 Too Many Requests: Rate limit exceeded. Retry after {retry_after} seconds.",
                    recipient=original_recipient,
                )

            if status_code == 400:
                return DeliveryResult(
                    success=False,
                    error=f"400 Bad Request: {response.json().get('description', 'Invalid request')}",
                    recipient=original_recipient,
                )

            data = response.json()

            if not data.get("ok"):
                return DeliveryResult(
                    success=False,
                    error=data.get("description", "Unknown error"),
                    recipient=original_recipient,
                )

            return DeliveryResult(
                success=True,
                message_id=data["result"]["message_id"],
                recipient=original_recipient,
            )

        except requests.exceptions.Timeout:
            return DeliveryResult(
                success=False,
                error="Request timed out",
                recipient=original_recipient,
            )
        except requests.exceptions.RequestException as e:
            return DeliveryResult(
                success=False,
                error=f"Request failed: {str(e)}",
                recipient=original_recipient,
            )

    def get_updates(self, offset: Optional[int] = None) -> list[dict]:
        """Fetch new updates from Telegram bot."""
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"{get_bot_api()}/getUpdates",
                params=params,
                timeout=35,
            )
            data = response.json()
            if not data.get("ok"):
                return []
            return data.get("result", [])
        except requests.exceptions.RequestException:
            return []
