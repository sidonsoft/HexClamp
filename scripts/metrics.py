#!/usr/bin/env python3
"""HexClamp quality metrics dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

from agents.store import STATE_DIR, RUNS_DIR, read_json


@dataclass
class Metrics:
    tasks_completed: int
    verified_results: int
    partial_results: int
    open_loops: int
    queued_events: int
    circuit_breaker_trips: int
    avg_loop_duration_seconds: float


def _parse_timestamp(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _iter_run_payloads() -> list[dict]:
    payloads: list[dict] = []
    if not RUNS_DIR.exists():
        return payloads
    for path in sorted(RUNS_DIR.glob("run-*.json")):
        try:
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return payloads


def collect_metrics() -> Metrics:
    runs = _iter_run_payloads()
    durations: list[float] = []

    for payload in runs:
        # Prefer an explicit duration if one is present in future run payloads.
        started_at = payload.get("started_at")
        finished_at = payload.get("finished_at")
        if isinstance(started_at, str) and isinstance(finished_at, str):
            start_dt = _parse_timestamp(started_at)
            end_dt = _parse_timestamp(finished_at)
            if start_dt and end_dt:
                durations.append((end_dt - start_dt).total_seconds())

    state = read_json(STATE_DIR / "current_state.json", default={}) or {}
    open_loops = len(state.get("open_loops", []))
    queued_events = len(read_json(STATE_DIR / "event_queue.json", default=[]) or [])
    circuit_breaker = read_json(STATE_DIR / "circuit_breaker.json", default={}) or {}

    tasks_completed = sum(1 for payload in runs if payload.get("result") and payload.get("result", {}).get("verified"))
    verified_results = tasks_completed
    partial_results = sum(
        1
        for payload in runs
        if payload.get("result") and not payload.get("result", {}).get("verified")
    )

    return Metrics(
        tasks_completed=tasks_completed,
        verified_results=verified_results,
        partial_results=partial_results,
        open_loops=open_loops,
        queued_events=queued_events,
        circuit_breaker_trips=int(circuit_breaker.get("consecutive_errors", 0)),
        avg_loop_duration_seconds=mean(durations) if durations else 0.0,
    )


def format_dashboard(metrics: Metrics) -> str:
    return "\n".join(
        [
            "HexClamp Quality Metrics",
            "=" * 26,
            f"Tasks completed: {metrics.tasks_completed}",
            f"Verified results: {metrics.verified_results}",
            f"Partial results: {metrics.partial_results}",
            f"Open loops: {metrics.open_loops}",
            f"Queued events: {metrics.queued_events}",
            f"Circuit breaker errors: {metrics.circuit_breaker_trips}",
            f"Average loop duration (s): {metrics.avg_loop_duration_seconds:.1f}",
        ]
    )


def main() -> int:
    metrics = collect_metrics()
    print(format_dashboard(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
