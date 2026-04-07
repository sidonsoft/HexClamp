"""Tests for HexClamp loop."""

import pytest

from hexclamp.loop import HexClampLoop, HexClampAgent
from hexclamp.models import Action, Result, LoopStatus, ActionType
from pathlib import Path


class TestLoopBasics:
    """Basic loop tests."""

    def test_loop_init(self, loop):
        """Test loop initialization."""
        assert loop is not None
        assert isinstance(loop.store.workspace, Path)

    def test_get_status(self, loop):
        """Test getting status."""
        status = loop.get_status()
        assert "total" in status
        assert "open" in status
        assert "completed" in status


class TestLoopEnqueue:
    """Tests for enqueue functionality."""

    def test_enqueue(self, loop):
        """Test enqueueing a task."""
        loop_obj = loop.enqueue("Test task")
        assert loop_obj is not None
        assert loop_obj.description == "Test task"
        assert loop_obj.status == LoopStatus.OPEN

    def test_enqueue_multiple(self, loop):
        """Test enqueueing multiple tasks."""
        loop.enqueue("Task 1")
        loop.enqueue("Task 2")
        loop.enqueue("Task 3")

        status = loop.get_status()
        assert status["total"] == 3


class TestLoopExecution:
    """Tests for loop execution."""

    def test_run_cycle(self, loop):
        """Test running a cycle."""
        loop.enqueue("Task 1")
        loop.enqueue("Task 2")

        processed = loop.run_cycle()
        assert len(processed) == 2

        status = loop.get_status()
        assert status["completed"] == 2

    def test_cycle_empty(self, loop):
        """Test running cycle with no tasks."""
        processed = loop.run_cycle()
        assert len(processed) == 0
