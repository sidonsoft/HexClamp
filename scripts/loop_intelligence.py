#!/usr/bin/env python3
"""Loop intelligence - analyze and rank open loops.

Usage:
    python3 scripts/loop_intelligence.py [--show-all] [--stale-only] [--format {table,json}]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Any
from types import SimpleNamespace

BASE = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "agents"))

from planner import rank_open_loops, _is_stale, _calculate_urgency_score


def dict_to_loop(d: dict) -> Any:
    """Convert dict to SimpleNamespace (loop-like object)."""
    return SimpleNamespace(**d)


def load_loops() -> list[Any]:
    """Load open loops from state file."""
    loops_file = BASE / "state" / "open_loops.json"
    if not loops_file.exists():
        return []
    
    data = json.loads(loops_file.read_text(encoding="utf-8"))
    return [dict_to_loop(item) for item in data]


def format_table(loops: list[Any], show_scores: bool = False) -> str:
    """Format loops as a table."""
    lines = []
    lines.append("=" * 100)
    lines.append(f"{'ID':<36} {'Status':<8} {'Priority':<8} {'Owner':<12} {'Evidence':<10} {'Blockers':<8}")
    lines.append("-" * 100)
    
    for i, loop in enumerate(loops):
        stale_mark = "⚠️" if _is_stale(loop) else ""
        evidence_count = len(loop.evidence) if hasattr(loop, "evidence") else 0
        blocker_count = len(loop.blocked_by) if hasattr(loop, "blocked_by") else 0
        lines.append(
            f"{loop.id[:36]:<36} "
            f"{loop.status:<8} "
            f"{getattr(loop, 'priority', 'normal'):<8} "
            f"{getattr(loop, 'owner', 'unknown'):<12} "
            f"{evidence_count:>8} "
            f"{blocker_count:>8}"
            f"{stale_mark}"
        )
        next_step = getattr(loop, "next_step", "No next step")[:60]
        lines.append(f"  → {next_step}")
        if show_scores:
            score = _calculate_urgency_score(loop)
            lines.append(f"  Score: {score}")
        lines.append("")
    
    lines.append("=" * 100)
    lines.append(f"Total: {len(loops)} loops")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze and rank open loops")
    parser.add_argument("--show-all", "-a", action="store_true", help="Show all loops including resolved")
    parser.add_argument("--stale-only", "-s", action="store_true", help="Show only stale loops")
    parser.add_argument("--format", "-f", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--show-scores", action="store_true", help="Show urgency scores")
    args = parser.parse_args()
    
    loops = load_loops()
    
    if not loops:
        print("No loops found.")
        return 0
    
    # Filter based on args
    if not args.show_all:
        loops = [l for l in loops if getattr(l, "status", "") in {"open", "blocked"}]
    
    if args.stale_only:
        loops = [l for l in loops if _is_stale(l)]
    
    # Rank the loops
    ranked = rank_open_loops(loops)
    
    if args.format == "json":
        # Convert back to dicts for JSON output
        output = [{k: getattr(loop, k) for k in dir(loop) if not k.startswith("_")} for loop in ranked]
        print(json.dumps(output, indent=2, default=str))
    else:
        print(format_table(ranked, args.show_scores))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
