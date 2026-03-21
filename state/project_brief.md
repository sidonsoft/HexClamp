# Project Brief

## What this is

Hydra-Claw-Loop is an inspectable autonomous agent loop scaffold that separates observation, condensation, planning, execution, verification, and persistence. File-backed state makes all progress auditable and recoverable.

## Why it exists

To avoid prompt soup, reduce rediscovery, and make agent progress auditable and recoverable. Built as a scaffold that can be dropped into any codebase or workflow with minimal adaptation.

## Architecture

The loop is organized around six distinct responsibilities (observe → condense → decide → act → verify → persist), each with a defined input/output contract. Executors are pluggable and narrow in scope.

## Current phase

**Active development** — core loop implemented, all four executors (research, code, browser, messaging) wired up, CI/CD in place. Addressing known issues from code review before declaring v1.0 done.

## Operating constraints

- Keep state file-backed. Never hold open loops or events in memory only.
- Prefer condensed context over full rescans. Tokens are money.
- Require evidence for meaningful actions. "Done" means verified.
- All executors run under policy gates. Approval required for external sends.
- Circuit breaker trips after 3 consecutive errors to prevent runaway loops.

## What's working

- Research executor: grounded summaries into `state/recent_changes.md`
- Code executor: coding agent task briefs in `runs/code_tasks/`
- Browser executor: navigation and extraction stubs
- Messaging executor: draft/send with approval gate
- File-backed state with atomic JSON I/O
- Schema validation with disk-backed caching
- GitHub Actions CI: syntax checks + pytest on every push/PR

## What's not yet

- `system` executor (classified by planner but has no implementation)
- `wait` action type (declared in schema, no executor path)
- `enabled` policy flags not enforced by executor code
- Browser executor needs real visible-state evidence
- Messaging executor approval gate doesn't check `external_send.require_approval` policy
