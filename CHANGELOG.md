# Changelog

All notable changes to HexClamp will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-04-07

### Added

- Structured loop: Observe → Condense → Plan → Execute → Verify → Persist
- Event system with webhook support (GitHub, Slack, GitLab)
- Scheduler with cron and interval timers
- File-backed state management
- OpenClaw agent adapter
- Reference CLI agent implementation
- GitHub Actions CI/CD

### Components

- `models.py`: Event, Action, Result, OpenLoop data classes
- `store.py`: HexClampStore for persistent state
- `loop.py`: HexClampLoop orchestrator
- `agent.py`: Abstract agent interface
- `scheduler.py`: TimerManager and Timer classes
- `webhook.py`: WebhookReceiver with signature verification
- `adapters/openclaw.py`: OpenClaw integration
