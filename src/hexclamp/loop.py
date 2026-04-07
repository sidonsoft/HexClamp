"""HexClamp main loop orchestrator."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hexclamp.models import (
    Action,
    ActionType,
    Event,
    EventType,
    LoopStatus,
    OpenLoop,
    Result,
)
from hexclamp.store import HexClampStore

logger = logging.getLogger(__name__)


class HexClampAgent(ABC):
    """Abstract agent interface."""

    @abstractmethod
    def execute(self, action: Action) -> Result:
        """Execute an action and return result."""
        pass

    @abstractmethod
    def get_workspace(self) -> Path:
        """Get the agent's workspace path."""
        pass


class HexClampLoop:
    """Main loop orchestrator."""

    def __init__(self, workspace: Path, agent: HexClampAgent) -> None:
        """Initialize loop."""
        self.workspace = workspace
        self.agent = agent
        self.store = HexClampStore(workspace / ".hexclamp")
        self._running = False

    def enqueue(self, description: str, source: str = "cli") -> OpenLoop:
        """Enqueue a new task."""
        event = Event(
            id=f"evt-{datetime.now(timezone.utc).timestamp()}",
            type=EventType.TASK,
            content=description,
            metadata={"source": source},
        )
        self.store.save_event(event)

        loop = OpenLoop(
            id=f"loop-{datetime.now(timezone.utc).timestamp()}",
            event_id=event.id,
            description=description,
        )
        self.store.save_loop(loop)

        logger.info(f"Enqueued: {description}")
        return loop

    def run_cycle(self) -> list[OpenLoop]:
        """Run one cycle of the loop."""
        if self._running:
            logger.warning("Loop already running")
            return []

        self._running = True
        processed = []

        try:
            # Get pending loops
            loops = self.store.get_open_loops(status=LoopStatus.OPEN, limit=5)

            for loop in loops:
                try:
                    result = self._execute_loop(loop)
                    if result:
                        processed.append(loop)
                except Exception as e:
                    logger.exception(f"Error processing loop {loop.id}: {e}")
                    loop.status = LoopStatus.FAILED
                    loop.result = Result(
                        success=False,
                        message=f"Error: {e}",
                    )
                    self.store.save_loop(loop)
                    processed.append(loop)

        finally:
            self._running = False

        return processed

    def _execute_loop(self, loop: OpenLoop) -> bool:
        """Execute a single loop."""
        # Update status to in_progress
        loop.status = LoopStatus.IN_PROGRESS
        self.store.save_loop(loop)

        # Create action
        action = Action(
            id=f"action-{datetime.now(timezone.utc).timestamp()}",
            type=ActionType.CODE,
            description=loop.description,
            priority=loop.priority,
        )
        loop.action_id = action.id

        # Execute
        result = self.agent.execute(action)
        loop.result = result

        if result.success:
            loop.status = LoopStatus.COMPLETED
        else:
            loop.status = LoopStatus.FAILED

        self.store.save_loop(loop)
        self.store.save_result(loop.id, result)

        logger.info(f"Loop {loop.id}: {loop.status.value}")
        return True

    def get_status(self) -> dict[str, Any]:
        """Get loop status summary."""
        all_loops = self.store.get_all_loops()
        return {
            "total": len(all_loops),
            "open": len([lp for lp in all_loops if lp.status == LoopStatus.OPEN]),
            "in_progress": len([lp for lp in all_loops if lp.status == LoopStatus.IN_PROGRESS]),
            "completed": len([lp for lp in all_loops if lp.status == LoopStatus.COMPLETED]),
            "failed": len([lp for lp in all_loops if lp.status == LoopStatus.FAILED]),
        }
