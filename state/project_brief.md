# Project Brief

## What this is

Hydra-Claw-Loop is an inspectable autonomous agent loop scaffold that separates observation, condensation, planning, execution, verification, and persistence. File-backed state makes all progress auditable and recoverable.

## Why it exists

To avoid prompt soup, reduce rediscovery, and make agent progress auditable and recoverable. Built as a scaffold that can be dropped into any codebase or workflow with minimal adaptation.

## Architecture

The loop is organized around six distinct responsibilities (observe → condense → decide → act → verify → persist), each with a defined input/output contract. Executors are pluggable and narrow in scope.

## Current phase

**v1.0** — all four executors implemented and reviewed, CI/CD in place, all code review findings resolved. Messaging delivery wired (Telegram Bot API direct, sentinel approval).

## Operating constraints

- Keep state file-backed. Never hold open loops or events in memory only.
- Prefer condensed context over full rescans. Tokens are money.
- Require evidence for meaningful actions. "Done" means verified.
- All executors run under policy gates. Approval required for external sends.
- Circuit breaker trips after 3 consecutive errors to prevent runaway loops.

## What's working

- Research executor: grounded summaries into `state/recent_changes.md`
- Code executor: coding agent task briefs in `runs/code_tasks/`
- Browser executor: Playwright headless Chromium, navigates, screenshots to `screenshot.png`, extracts text to `content.txt`, URL validation (schemes + IPv4/IPv6 private ranges)
- File-backed state with atomic JSON I/O
- Schema validation with disk-backed caching
- GitHub Actions CI: syntax checks + pytest + ruff linting on every push/PR
- Circuit breaker with persisted state (survives restarts)
- End-to-end integration tests (47 tests passing)

## What's not yet

- `wait` action type (declared in schema, no executor path)
- Status dashboard (visual progress/loop overview)
- End-to-end test coverage with real coding agents (current E2E tests use mocks/stubs)

## v1.0 scope

MVP is a loop that can observe, plan, execute (research + code + browser), verify, and persist — fully file-backed, auditable, and recoverable. Messaging delivery is desirable but not blocking.
