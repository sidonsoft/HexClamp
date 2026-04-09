"""HexClamp webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""

    # GitHub
    GITHUB_PUSH = "push"
    GITHUB_PULL_REQUEST = "pull_request"
    GITHUB_ISSUE_COMMENT = "issue_comment"
    GITHUB_CHECK_RUN = "check_run"
    GITHUB_CHECK_SUITE = "check_suite"

    # Slack
    SLACK_MESSAGE = "message"
    SLACK_APP_MENTION = "app_mention"

    # GitLab
    GITLAB_PUSH = "gitlab_push"


@dataclass
class WebhookPayload:
    """Parsed webhook payload."""

    event: WebhookEvent
    data: dict[str, Any]
    headers: dict[str, str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event": self.event.value,
            "data": self.data,
            "headers": self.headers,
            "timestamp": self.timestamp.isoformat(),
        }


class WebhookHandler:
    """Handler for webhook events."""

    def __init__(self, callback: Callable[[WebhookPayload], None]) -> None:
        """Initialize handler."""
        self.callback = callback

    def handle(self, payload: WebhookPayload) -> None:
        """Handle a webhook payload."""
        try:
            self.callback(payload)
        except Exception as e:
            logger.exception(f"Webhook handler error: {e}")


class WebhookReceiver:
    """Webhook receiver with signature verification."""

    def __init__(self, secret: str | None = None) -> None:
        """Initialize webhook receiver."""
        self.secret = secret
        self._handlers: dict[WebhookEvent, list[WebhookHandler]] = {}
        self._received: list[WebhookPayload] = []

    def add_handler(self, event: WebhookEvent, handler: WebhookHandler) -> None:
        """Add a handler for an event type."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def on(self, event: WebhookEvent) -> Callable:
        """Decorator to register a handler."""
        def decorator(func: Callable[[WebhookPayload], None]) -> Callable:
            self.add_handler(event, WebhookHandler(func))
            return func
        return decorator

    def verify_github(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature."""
        if not self.secret:
            return True

        expected = "sha256=" + hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def verify_slack(
        self,
        timestamp: str,
        signature: str,
        body: bytes,
    ) -> bool:
        """Verify Slack webhook signature."""
        if not self.secret:
            return True

        if abs(time.time() - float(timestamp)) > 60 * 5:
            logger.warning("Slack webhook timestamp too old")
            return False

        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            self.secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def receive_github(
        self,
        event: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        signature: str | None = None,
        raw_payload: bytes | None = None,
    ) -> WebhookPayload | None:
        """Receive a GitHub webhook."""
        try:
            webhook_event = WebhookEvent(event)
        except ValueError:
            logger.warning(f"Unknown GitHub event: {event}")
            return None

        payload_obj = WebhookPayload(
            event=webhook_event,
            data=payload,
            headers=headers,
        )

        if signature and raw_payload and not self.verify_github(raw_payload, signature):
            logger.warning("GitHub signature verification failed")
            return None

        self._received.append(payload_obj)
        self._dispatch(payload_obj)
        return payload_obj

    def receive_slack(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        timestamp: str | None = None,
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> WebhookPayload | None:
        """Receive a Slack webhook."""
        event_type = payload.get("event", {}).get("type", "message")
        try:
            webhook_event = WebhookEvent(f"slack_{event_type}")
        except ValueError:
            webhook_event = WebhookEvent.SLACK_MESSAGE

        payload_obj = WebhookPayload(
            event=webhook_event,
            data=payload,
            headers=headers,
        )

        if signature and timestamp and raw_body:
            if not self.verify_slack(timestamp, signature, raw_body):
                logger.warning("Slack signature verification failed")
                return None

        self._received.append(payload_obj)
        self._dispatch(payload_obj)
        return payload_obj

    def receive_gitlab(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> WebhookPayload:
        """Receive a GitLab webhook."""
        payload_obj = WebhookPayload(
            event=WebhookEvent.GITLAB_PUSH,
            data=payload,
            headers=headers,
        )
        self._received.append(payload_obj)
        self._dispatch(payload_obj)
        return payload_obj

    def _dispatch(self, payload: WebhookPayload) -> None:
        """Dispatch payload to handlers."""
        handlers = self._handlers.get(payload.event, [])
        for handler in handlers:
            handler.handle(payload)

    def get_statistics(self) -> dict[str, Any]:
        """Get webhook statistics."""
        return {
            "total_received": len(self._received),
            "by_event": {
                event.value: len([p for p in self._received if p.event == event])
                for event in WebhookEvent
            },
        }


def create_github_webhook(
    secret: str | None = None,
    event_handlers: dict[str, Callable[[WebhookPayload], None]] | None = None,
) -> WebhookReceiver:
    """Create a GitHub webhook receiver."""
    receiver = WebhookReceiver(secret=secret)
    if event_handlers:
        for event, handler in event_handlers.items():
            try:
                receiver.add_handler(WebhookEvent(event), WebhookHandler(handler))
            except ValueError:
                logger.warning(f"Unknown event type: {event}")
    return receiver


def create_slack_webhook(
    secret: str | None = None,
    event_handlers: dict[str, Callable[[WebhookPayload], None]] | None = None,
) -> WebhookReceiver:
    """Create a Slack webhook receiver."""
    receiver = WebhookReceiver(secret=secret)
    if event_handlers:
        for event, handler in event_handlers.items():
            try:
                receiver.add_handler(WebhookEvent(event), WebhookHandler(handler))
            except ValueError:
                logger.warning(f"Unknown event type: {event}")
    return receiver
