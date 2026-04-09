"""OpenClaw agent adapter."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class AdapterStatus(str, Enum):
    """Adapter connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class AgentResponse:
    """Response from an agent."""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error: str | None = None


class OpenClawAdapter:
    """Adapter for OpenClaw agent integration."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8080",
        api_key: str | None = None,
        timeout: int = 300,
        max_retries: int = 3,
        mock: bool = False,
    ) -> None:
        """Initialize OpenClaw adapter."""
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.mock = mock
        self._status = AdapterStatus.DISCONNECTED
        self._request_count = 0

    @property
    def status(self) -> AdapterStatus:
        """Get adapter status."""
        return self._status

    @property
    def request_count(self) -> int:
        """Get number of requests made."""
        return self._request_count

    def connect(self) -> bool:
        """Test connection to OpenClaw."""
        if self.mock:
            self._status = AdapterStatus.CONNECTED
            return True

        try:
            request = Request(f"{self.endpoint}/health")
            if self.api_key:
                request.add_header("Authorization", f"Bearer {self.api_key}")

            with urlopen(request, timeout=5) as response:
                if response.status == 200:
                    self._status = AdapterStatus.CONNECTED
                    return True

        except URLError as e:
            logger.warning(f"OpenClaw connection failed: {e}")

        self._status = AdapterStatus.ERROR
        return False

    def send_task(self, task: str, context: dict[str, Any] | None = None) -> AgentResponse:
        """Send a task to the agent."""
        self._request_count += 1

        if self.mock:
            return self._mock_response(task)

        payload = {
            "task": task,
            "context": context or {},
            "timestamp": time.time(),
        }

        for attempt in range(self.max_retries):
            try:
                request = Request(
                    f"{self.endpoint}/api/execute",
                    data=json.dumps(payload).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                    },
                )

                with urlopen(request, timeout=self.timeout) as response:
                    data = response.read()
                    result = self._parse_response(data)
                    self._status = AdapterStatus.CONNECTED
                    return result

            except URLError as e:
                logger.warning(f"OpenClaw request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        self._status = AdapterStatus.ERROR
        return AgentResponse(
            success=False,
            message="Request failed after retries",
            error=f"Connection failed after {self.max_retries} attempts",
        )

    def _parse_response(self, data: bytes) -> AgentResponse:
        """Parse agent response."""
        import json

        try:
            parsed = json.loads(data)
            return AgentResponse(
                success=parsed.get("success", False),
                message=parsed.get("message", ""),
                data=parsed.get("data"),
                error=parsed.get("error"),
            )
        except json.JSONDecodeError:
            return AgentResponse(
                success=True,
                message=data.decode("utf-8", errors="replace"),
            )

    def _mock_response(self, task: str) -> AgentResponse:
        """Generate mock response for testing."""
        return AgentResponse(
            success=True,
            message=f"Mock executed: {task[:50]}...",
            data={"task": task, "mock": True},
        )

    def execute_code(self, code: str) -> AgentResponse:
        """Execute code via agent."""
        return self.send_task(
            f"Execute code: {code}",
            context={"type": "code", "code": code},
        )

    def execute_research(self, query: str) -> AgentResponse:
        """Execute research query via agent."""
        return self.send_task(
            f"Research: {query}",
            context={"type": "research", "query": query},
        )


class OpenClawConnectionPool:
    """Connection pool for OpenClaw adapters."""

    def __init__(self, max_size: int = 5) -> None:
        """Initialize connection pool."""
        self.max_size = max_size
        self._adapters: list[OpenClawAdapter] = []

    def get_adapter(self) -> OpenClawAdapter | None:
        """Get an available adapter."""
        for adapter in self._adapters:
            if adapter.status == AdapterStatus.CONNECTED:
                return adapter

        if len(self._adapters) < self.max_size:
            adapter = OpenClawAdapter()
            if adapter.connect():
                self._adapters.append(adapter)
                return adapter

        return None

    def release_adapter(self, adapter: OpenClawAdapter) -> None:
        """Release an adapter back to the pool."""
        pass  # Adapters stay in pool

    def close_all(self) -> None:
        """Close all adapters."""
        for adapter in self._adapters:
            adapter._status = AdapterStatus.DISCONNECTED
        self._adapters.clear()
