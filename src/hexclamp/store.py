"""HexClamp file-backed state store."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from hexclamp.models import Event, LoopStatus, OpenLoop, Result

logger = logging.getLogger(__name__)


class HexClampStore:
    """File-backed state management."""

    def __init__(self, workspace: Path) -> None:
        """Initialize store."""
        self.workspace = workspace
        self.events_dir = workspace / "events"
        self.loops_dir = workspace / "loops"
        self.results_dir = workspace / "results"

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        for directory in [self.events_dir, self.loops_dir, self.results_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path) -> dict[str, object]:
        """Read JSON file safely."""
        try:
            data: dict[str, object] = json.loads(path.read_text())
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {path}: {e}")
            return {}

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON file atomically."""
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2))
        temp.rename(path)

    # Event operations
    def save_event(self, event: Event) -> None:
        """Save an event."""
        path = self.events_dir / f"{event.id}.json"
        self._write_json(path, event.to_dict())

    def get_event(self, event_id: str) -> Event | None:
        """Get an event by ID."""
        path = self.events_dir / f"{event_id}.json"
        if not path.exists():
            return None
        data = self._read_json(path)
        return Event.from_dict(data) if data else None

    def get_all_events(self) -> list[Event]:
        """Get all events."""
        events = []
        for path in self.events_dir.glob("*.json"):
            data = self._read_json(path)
            if data:
                events.append(Event.from_dict(data))
        return sorted(events, key=lambda e: e.timestamp, reverse=True)

    # Loop operations
    def save_loop(self, loop: OpenLoop) -> None:
        """Save a loop."""
        loop.updated_at = datetime.now(timezone.utc)
        path = self.loops_dir / f"{loop.id}.json"
        self._write_json(path, loop.to_dict())

    def get_loop(self, loop_id: str) -> OpenLoop | None:
        """Get a loop by ID."""
        path = self.loops_dir / f"{loop_id}.json"
        if not path.exists():
            return None
        data = self._read_json(path)
        return OpenLoop.from_dict(data) if data else None

    def get_open_loops(
        self,
        status: LoopStatus | None = None,
        limit: int | None = None,
    ) -> list[OpenLoop]:
        """Get open loops, optionally filtered by status."""
        loops = []
        for path in self.loops_dir.glob("*.json"):
            data = self._read_json(path)
            if data:
                loop = OpenLoop.from_dict(data)
                if status is None or loop.status == status:
                    loops.append(loop)

        loops.sort(key=lambda lp: (-lp.priority, lp.created_at))

        if limit:
            loops = loops[:limit]

        return loops

    def get_all_loops(self) -> list[OpenLoop]:
        """Get all loops."""
        return self.get_open_loops(status=None)

    def get_loop_by_event(self, event_id: str) -> OpenLoop | None:
        """Get loop associated with an event."""
        for path in self.loops_dir.glob("*.json"):
            data = self._read_json(path)
            if data and data.get("event_id") == event_id:
                return OpenLoop.from_dict(data)
        return None

    def delete_loop(self, loop_id: str) -> bool:
        """Delete a loop."""
        path = self.loops_dir / f"{loop_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # Result operations
    def save_result(self, loop_id: str, result: Result) -> None:
        """Save a result for a loop."""
        path = self.results_dir / f"{loop_id}.json"
        self._write_json(path, result.to_dict())

    def get_result(self, loop_id: str) -> Result | None:
        """Get result for a loop."""
        path = self.results_dir / f"{loop_id}.json"
        if not path.exists():
            return None
        data = self._read_json(path)
        return Result.from_dict(data) if data else None
