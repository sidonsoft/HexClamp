# HexClamp

**Agent Integration Platform**

[![Tests](https://github.com/sidonsoft/HexClamp/actions/workflows/ci.yml/badge.svg)](https://github.com/sidonsoft/HexClamp/actions/workflows/ci.yml)

## Overview

HexClamp is an agent integration platform that provides structured loops, event handling, and state management for autonomous agents.

## Features

- **Structured Loop**: Observe → Condense → Plan → Execute → Verify → Persist
- **Event System**: Webhooks for GitHub, Slack, GitLab
- **Scheduling**: Cron-based and interval timers
- **State Management**: File-backed persistent state
- **Agent Adapters**: OpenClaw and reference CLI agent

## Installation

```bash
pip install hexclamp
```

Or for development:

```bash
git clone https://github.com/sidonsoft/HexClamp
cd HexClamp
pip install -e ".[dev]"
```

## Quick Start

```python
from hexclamp.loop import HexClampLoop
from hexclamp.agent import CLIAgent
from pathlib import Path

# Create agent and loop
agent = CLIAgent(workspace="/path/to/workspace")
loop = HexClampLoop(Path("/path/to/workspace"), agent)

# Enqueue a task
loop.enqueue("Read the README file")

# Run cycle
loop.run_cycle()
```

## CLI Usage

```bash
# Initialize workspace
hexclamp init

# Enqueue a task
hexclamp enqueue "Fix the login bug"

# Run cycle
hexclamp run

# Check status
hexclamp status
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              HexClamp Loop                   │
├─────────────────────────────────────────────┤
│  Observe → Condense → Plan → Execute → ... │
└─────────────────────────────────────────────┘
```

## Components

| Component | Description |
|-----------|-------------|
| `models.py` | Data classes (Event, Action, Result, OpenLoop) |
| `store.py` | File-backed state management |
| `loop.py` | Main loop orchestrator |
| `agent.py` | Agent interface and CLI reference |
| `scheduler.py` | Timer and schedule management |
| `webhook.py` | Webhook receiver (GitHub, Slack, GitLab) |
| `adapters/` | External agent adapters (OpenClaw) |

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/

# Format
ruff format src/
```

## License

Apache 2.0
