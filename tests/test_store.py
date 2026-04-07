"""Tests for HexClamp store."""

import pytest
from datetime import datetime, timezone

from hexclamp.store import HexClampStore
from hexclamp.models import Event, OpenLoop, Result, LoopStatus, EventType


class TestStoreEvents:
    """Tests for event storage."""

    def test_save_event(self, store):
        """Test saving an event."""
        event = Event(
            id="evt-1",
            type=EventType.TASK,
            content="Test task",
        )
        store.save_event(event)

        retrieved = store.get_event("evt-1")
        assert retrieved is not None
        assert retrieved.id == "evt-1"
        assert retrieved.content == "Test task"

    def test_get_nonexistent_event(self, store):
        """Test getting non-existent event."""
        assert store.get_event("nonexistent") is None

    def test_get_all_events(self, store):
        """Test getting all events."""
        for i in range(3):
            event = Event(
                id=f"evt-{i}",
                type=EventType.TASK,
                content=f"Task {i}",
            )
            store.save_event(event)

        events = store.get_all_events()
        assert len(events) == 3


class TestStoreLoops:
    """Tests for loop storage."""

    def test_save_loop(self, store):
        """Test saving a loop."""
        loop = OpenLoop(
            id="loop-1",
            event_id="evt-1",
            description="Test loop",
        )
        store.save_loop(loop)

        retrieved = store.get_loop("loop-1")
        assert retrieved is not None
        assert retrieved.description == "Test loop"

    def test_get_open_loops(self, store):
        """Test getting open loops."""
        # Create open and completed loops
        for i in range(3):
            loop = OpenLoop(
                id=f"loop-{i}",
                event_id=f"evt-{i}",
                description=f"Loop {i}",
            )
            store.save_loop(loop)

        # Complete one
        completed = store.get_loop("loop-0")
        completed.status = LoopStatus.COMPLETED
        store.save_loop(completed)

        open_loops = store.get_open_loops(status=LoopStatus.OPEN)
        assert len(open_loops) == 2

    def test_get_loop_by_event(self, store):
        """Test getting loop by event ID."""
        loop = OpenLoop(
            id="loop-1",
            event_id="evt-1",
            description="Test",
        )
        store.save_loop(loop)

        found = store.get_loop_by_event("evt-1")
        assert found is not None
        assert found.id == "loop-1"

    def test_delete_loop(self, store):
        """Test deleting a loop."""
        loop = OpenLoop(
            id="loop-1",
            event_id="evt-1",
            description="To delete",
        )
        store.save_loop(loop)

        assert store.delete_loop("loop-1") is True
        assert store.get_loop("loop-1") is None


class TestStoreResults:
    """Tests for result storage."""

    def test_save_result(self, store):
        """Test saving a result."""
        result = Result(
            success=True,
            message="Done",
        )
        store.save_result("loop-1", result)

        retrieved = store.get_result("loop-1")
        assert retrieved is not None
        assert retrieved.success is True
