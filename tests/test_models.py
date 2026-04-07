"""Tests for HexClamp models."""

import pytest
from datetime import datetime, timezone

from hexclamp.models import (
    Event,
    Action,
    Result,
    OpenLoop,
    LoopStatus,
    EventType,
    ActionType,
)


class TestEvent:
    """Tests for Event model."""

    def test_create_event(self):
        """Test creating an event."""
        event = Event(
            id="evt-1",
            type=EventType.TASK,
            content="Test task",
        )
        assert event.id == "evt-1"
        assert event.type == EventType.TASK
        assert event.content == "Test task"
        assert isinstance(event.timestamp, datetime)

    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = Event(
            id="evt-1",
            type=EventType.TASK,
            content="Test task",
        )
        data = event.to_dict()
        assert data["id"] == "evt-1"
        assert data["type"] == "task"
        assert data["content"] == "Test task"

    def test_event_from_dict(self):
        """Test creating event from dict."""
        data = {
            "id": "evt-1",
            "type": "task",
            "content": "Test task",
            "timestamp": "2026-04-07T12:00:00+00:00",
            "metadata": {},
        }
        event = Event.from_dict(data)
        assert event.id == "evt-1"
        assert event.type == EventType.TASK


class TestAction:
    """Tests for Action model."""

    def test_create_action(self):
        """Test creating an action."""
        action = Action(
            id="action-1",
            type=ActionType.CODE,
            description="Fix bug",
            priority=8,
        )
        assert action.id == "action-1"
        assert action.type == ActionType.CODE
        assert action.priority == 8

    def test_action_to_dict(self):
        """Test converting action to dict."""
        action = Action(
            id="action-1",
            type=ActionType.RESEARCH,
            description="Find files",
        )
        data = action.to_dict()
        assert data["id"] == "action-1"
        assert data["type"] == "research"


class TestResult:
    """Tests for Result model."""

    def test_create_result(self):
        """Test creating a result."""
        result = Result(
            success=True,
            message="Done",
            evidence={"files": ["a.py"]},
        )
        assert result.success is True
        assert result.message == "Done"
        assert result.evidence["files"] == ["a.py"]

    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = Result(success=False, message="Failed")
        data = result.to_dict()
        assert data["success"] is False
        assert data["message"] == "Failed"


class TestOpenLoop:
    """Tests for OpenLoop model."""

    def test_create_loop(self):
        """Test creating an open loop."""
        loop = OpenLoop(
            id="loop-1",
            event_id="evt-1",
            description="Fix bug",
        )
        assert loop.id == "loop-1"
        assert loop.status == LoopStatus.OPEN
        assert loop.priority == 5

    def test_loop_to_dict(self):
        """Test converting loop to dict."""
        loop = OpenLoop(
            id="loop-1",
            event_id="evt-1",
            description="Fix bug",
            status=LoopStatus.COMPLETED,
        )
        data = loop.to_dict()
        assert data["id"] == "loop-1"
        assert data["status"] == "completed"

    def test_loop_from_dict(self):
        """Test creating loop from dict."""
        data = {
            "id": "loop-1",
            "event_id": "evt-1",
            "description": "Test",
            "status": "open",
            "priority": 7,
            "action_id": None,
            "result": None,
            "created_at": "2026-04-07T12:00:00+00:00",
            "updated_at": "2026-04-07T12:00:00+00:00",
            "metadata": {},
        }
        loop = OpenLoop.from_dict(data)
        assert loop.id == "loop-1"
        assert loop.status == LoopStatus.OPEN
        assert loop.priority == 7
