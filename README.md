# hydra-claw-loop

A practical scaffold for an inspectable agent loop.

## Goal

Build a system that stays coherent over time by separating:
- observation
- condensation
- planning
- execution
- verification
- persistence

The first version should optimize for:
- inspectability
- recoverability
- low token burn
- narrow contracts
- state that survives bad runs

## Core loop

Observe -> Condense -> Decide -> Act -> Verify -> Persist

## Design principles

1. Raw inputs get normalized before use.
2. Condensed state is the default context, not the whole world.
3. Executors have narrow authority and clear contracts.
4. Verification is mandatory for meaningful actions.
5. File-backed state beats invisible prompt state.
6. Persistent briefs and open loops prevent rediscovery.

## Initial build order

1. Directory scaffold
2. JSON schemas
3. File IO helpers
4. Schema validation
5. Observer
6. Condenser
7. Planner
8. One executor
9. Verifier
10. Main loop runner

## Current vertical slices

- Research: grounded summaries into `state/recent_changes.md`
- Code: creates task brief artifacts in `runs/code_tasks/`

## Suggested next executor

After code, add browser execution with real visible-state evidence.

## Top-level structure

```text
hydra-claw-loop/
  README.md
  config/
  state/
  memory/
  schemas/
  prompts/
  agents/
  runs/
```

## Current status

This repository contains the scaffold, starter schemas, prompt contracts, Python loop implementation, and executor/task tooling.

Generated runtime files (`runs/`, live `state/*.json`, `state/recent_changes.md`) are intentionally excluded from source control.

## Runtime bootstrap

Missing runtime state is recreated automatically when the loop runs.

Manual bootstrap:

```bash
python3 agents/loop.py init
# or
python3 scripts/bootstrap_runtime.py
```

This recreates:
- `state/current_state.json`
- `state/event_queue.json`
- `state/open_loops.json`
- `state/recent_changes.md`

## Testing

Run the full test suite:

```bash
make test
# or
python3 -m unittest discover -s tests -v
```

Current automated coverage includes:
- message parser regression tests
- planner ranking tests
- task completion verification tests
- runtime bootstrap tests
- one end-to-end enqueue → plan → task artifact integration test
