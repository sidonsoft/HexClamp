"""Test fixtures and configuration."""

import pytest
import tempfile
from pathlib import Path

from hexclamp.store import HexClampStore
from hexclamp.loop import HexClampLoop, HexClampAgent
from hexclamp.models import Action, Result


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_workspace):
    """Create a test store."""
    return HexClampStore(temp_workspace / ".hexclamp")


@pytest.fixture
def mock_agent():
    """Create a mock agent."""

    class MockAgent(HexClampAgent):
        def __init__(self):
            self.workspace = Path("/tmp")

        def execute(self, action: Action) -> Result:
            return Result(
                success=True,
                message=f"Mock executed: {action.description}",
                evidence={"action_id": action.id},
            )

        def get_workspace(self) -> Path:
            return self.workspace

    return MockAgent()


@pytest.fixture
def loop(temp_workspace, mock_agent):
    """Create a test loop."""
    return HexClampLoop(temp_workspace, mock_agent)
