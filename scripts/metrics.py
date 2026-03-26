#!/usr/bin/env python3
"""HexClamp quality metrics dashboard."""

from __future__ import annotations

import json
import argparse
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import mean
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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

    @property
    def completion_rate(self) -> float:
        total = self.tasks_completed + self.partial_results
        return (self.tasks_completed / total * 100.0) if total else 0.0

    @property
    def queue_pressure(self) -> int:
        return self.open_loops + self.queued_events


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


def format_dashboard_html(metrics: Metrics) -> str:
    cards = [
        ("Tasks completed", metrics.tasks_completed, "Verified task runs"),
        ("Verified results", metrics.verified_results, "Result records marked verified"),
        ("Partial results", metrics.partial_results, "Result records needing follow-up"),
        ("Open loops", metrics.open_loops, "Loops still in progress"),
        ("Queued events", metrics.queued_events, "Events waiting for a cycle"),
        ("Circuit breaker errors", metrics.circuit_breaker_trips, "Consecutive failures"),
    ]

    card_markup = "\n".join(
        f"""
        <section class="card">
          <div class="card-label">{escape(label)}</div>
          <div class="card-value">{escape(str(value))}</div>
          <div class="card-note">{escape(note)}</div>
        </section>
        """
        for label, value, note in cards
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>HexClamp Metrics Dashboard</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #07111f;
        --panel: rgba(10, 20, 35, 0.82);
        --panel-border: rgba(154, 184, 255, 0.18);
        --text: #e9f0ff;
        --muted: #96a6c6;
        --accent: #6fb1ff;
        --accent-strong: #9dd0ff;
        --danger: #ff8f8f;
        --good: #8be0a8;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(111, 177, 255, 0.18), transparent 32%),
          radial-gradient(circle at top right, rgba(139, 224, 168, 0.14), transparent 24%),
          linear-gradient(180deg, #091120 0%, #050a13 100%);
      }}
      .shell {{
        max-width: 1100px;
        margin: 0 auto;
        padding: 40px 24px 56px;
      }}
      .hero {{
        display: grid;
        gap: 16px;
        margin-bottom: 28px;
      }}
      .eyebrow {{
        color: var(--accent-strong);
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.78rem;
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2.2rem, 4vw, 4rem);
        line-height: 0.95;
      }}
      .subhead {{
        max-width: 72ch;
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.6;
      }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
        margin-bottom: 18px;
      }}
      .card, .panel {{
        background: var(--panel);
        border: 1px solid var(--panel-border);
        border-radius: 18px;
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
        backdrop-filter: blur(10px);
      }}
      .card {{
        padding: 18px;
      }}
      .card-label {{
        color: var(--muted);
        font-size: 0.88rem;
        margin-bottom: 10px;
      }}
      .card-value {{
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.04em;
      }}
      .card-note {{
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      .grid {{
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 18px;
      }}
      .panel {{
        padding: 20px;
      }}
      .panel h2 {{
        margin: 0 0 14px;
        font-size: 1.1rem;
      }}
      .metric-list {{
        display: grid;
        gap: 12px;
      }}
      .metric-row {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 0;
        border-bottom: 1px solid rgba(154, 184, 255, 0.12);
      }}
      .metric-row:last-child {{
        border-bottom: 0;
        padding-bottom: 0;
      }}
      .metric-name {{
        color: var(--muted);
      }}
      .metric-value {{
        font-weight: 700;
      }}
      .good {{
        color: var(--good);
      }}
      .warn {{
        color: var(--danger);
      }}
      .footer {{
        margin-top: 16px;
        color: var(--muted);
        font-size: 0.85rem;
      }}
      @media (max-width: 900px) {{
        .stats, .grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <div class="eyebrow">HexClamp Observability</div>
        <h1>Quality Metrics Dashboard</h1>
        <div class="subhead">
          A local web view over the file-backed loop state. Use this to spot throughput,
          verification health, and queue pressure without opening raw JSON.
        </div>
      </section>
      <section class="stats">
        {card_markup}
      </section>
      <section class="grid">
        <article class="panel">
          <h2>Health Summary</h2>
          <div class="metric-list">
            <div class="metric-row"><span class="metric-name">Completion rate</span><span class="metric-value good">{metrics.completion_rate:.1f}%</span></div>
            <div class="metric-row"><span class="metric-name">Queue pressure</span><span class="metric-value">{metrics.queue_pressure}</span></div>
            <div class="metric-row"><span class="metric-name">Average loop duration</span><span class="metric-value">{metrics.avg_loop_duration_seconds:.1f}s</span></div>
          </div>
        </article>
        <article class="panel">
          <h2>Source</h2>
          <div class="metric-list">
            <div class="metric-row"><span class="metric-name">State dir</span><span class="metric-value">{escape(str(STATE_DIR))}</span></div>
            <div class="metric-row"><span class="metric-name">Runs dir</span><span class="metric-value">{escape(str(RUNS_DIR))}</span></div>
            <div class="metric-row"><span class="metric-name">Generated</span><span class="metric-value">{escape(datetime.now().isoformat(timespec="seconds"))}</span></div>
          </div>
        </article>
      </section>
      <div class="footer">Refresh the page after each loop cycle to see updated metrics.</div>
    </main>
  </body>
</html>
"""


def create_handler():
    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route not in {"/", "/index.html"}:
                self.send_error(404, "Not found")
                return
            body = format_dashboard_html(collect_metrics()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return MetricsHandler


def serve_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), create_handler())
    print(f"Serving HexClamp metrics dashboard at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="HexClamp quality metrics dashboard")
    parser.add_argument("--web", action="store_true", help="Serve the dashboard over HTTP")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind when serving web UI")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind when serving web UI")
    args = parser.parse_args()

    if args.web:
        serve_dashboard(args.host, args.port)
        return 0

    metrics = collect_metrics()
    print(format_dashboard(metrics))
    print()
    print("Web UI:", f"http://{args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
