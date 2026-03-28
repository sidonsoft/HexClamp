"""Loop operations for HexClamp agent loop.

Handles loop lifecycle operations: creation, pruning, staleness detection.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from agents.models import OpenLoop
from agents.loop.state_loaders import load_loops, save_loops, replace_or_append_loop


def is_stale(loop: OpenLoop, max_age_hours: int = 24) -> bool:
    """Check if a loop is stale (too old without progress).
    
    Args:
        loop: The loop to check
        max_age_hours: Maximum age in hours before considered stale
        
    Returns:
        True if loop is stale, False otherwise
    """
    if not loop.updated_at:
        return False
    
    # Parse updated_at if string
    if isinstance(loop.updated_at, str):
        try:
            updated = datetime.fromisoformat(loop.updated_at.replace('Z', '+00:00'))
        except ValueError:
            return False
    else:
        updated = loop.updated_at
    
    age = datetime.now(timezone.utc) - updated
    return age > timedelta(hours=max_age_hours)


def prune_old_loops(max_age_hours: int = 24, max_loops: int = 100) -> int:
    """Remove stale loops and enforce max loop count.
    
    Args:
        max_age_hours: Remove loops older than this
        max_loops: Maximum number of loops to keep
        
    Returns:
        Number of loops removed
    """
    loops = load_loops()
    original_count = len(loops)
    
    # Filter out stale loops
    loops = [l for l in loops if not is_stale(l, max_age_hours)]
    
    # Enforce max count (keep newest)
    if len(loops) > max_loops:
        loops = loops[-max_loops:]
    
    removed = original_count - len(loops)
    
    if removed > 0:
        save_loops(loops)
    
    return removed


def get_active_loops() -> List[OpenLoop]:
    """Get all non-stale loops."""
    loops = load_loops()
    return [l for l in loops if not is_stale(l)]


def create_loop(
    task: str,
    requirements: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> OpenLoop:
    """Create a new open loop.
    
    Args:
        task: Task description
        requirements: List of requirements to satisfy
        metadata: Additional metadata
        
    Returns:
        New OpenLoop instance
    """
    loop = OpenLoop(
        task=task,
        requirements=requirements or [],
        metadata=metadata or {},
    )
    replace_or_append_loop(loop)
    return loop
