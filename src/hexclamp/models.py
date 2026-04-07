"""HexClamp data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Event types."""

    TASK = "task"
    WEBHOOK = "webhook"
    TIMER = "timer"
    MESSAGE = "message"


class ActionType(str, Enum):
    """Action types."""

    CODE = "code"
    RESEARCH = "research"
    MESSAGE = "message"
    VERIFY = "verify"


class LoopStatus(str, Enum):
    """Loop statuses."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Event:
    """Represents an incoming event."""

    id: str
    type: EventType
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=EventType(data["type"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Action:
    """Represents an action to be executed."""

    id: str
    type: ActionType
    description: str
    priority: int = 5
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "priority": self.priority,
            "args": self.args,
            "kwargs": self.kwargs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=ActionType(data["type"]),
            description=data["description"],
            priority=data.get("priority", 5),
            args=tuple(data.get("args", [])),
            kwargs=data.get("kwargs", {}),
        )


@dataclass
class Result:
    """Represents the result of an action."""

    success: bool
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Result":
        """Create from dictionary."""
        return cls(
            success=data["success"],
            message=data["message"],
            evidence=data.get("evidence", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class OpenLoop:
    """Represents an open task/loop."""

    id: str
    event_id: str
    description: str
    status: LoopStatus = LoopStatus.OPEN
    priority: int = 5
    action_id: str | None = None
    result: Result | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "action_id": self.action_id,
            "result": self.result.to_dict() if self.result else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenLoop":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            event_id=data["event_id"],
            description=data["description"],
            status=LoopStatus(data.get("status", "open")),
            priority=data.get("priority", 5),
            action_id=data.get("action_id"),
            result=Result.from_dict(data["result"]) if data.get("result") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )
