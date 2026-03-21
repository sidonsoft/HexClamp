# Contributing to HexClamp

## Getting started

```bash
# Clone
git clone https://github.com/sidonsoft/HexClamp
cd HexClamp

# Bootstrap runtime state
python3 agents/loop.py init

# Run tests
make test

# Lint + format check
ruff check .
ruff format --check .

# Type check
mypy agents/ scripts/ --ignore-missing-imports
```

## Branch conventions

- `main` — stable, deployable
- `fix/<issue-name>` — bug fixes (e.g., `fix/circuit-breaker-persistence`)
- `feat/<feature-name>` — new features (e.g., `feat/system-executor`)
- `chore/<name>` — maintenance, deps, CI (e.g., `chore/add-ruff`)
- `review/<issue-numbers>` — code review fixes (e.g., `review/6-16`)

## Commit style

Use clear, specific commit messages:

```
fix: correct planner/executor loop selection order

Execute the same loop that plan_next_actions selected, not the
last candidate from the all-loop list. Without this, the urgency
ranking is bypassed entirely.

Fixes #6
```

```
chore: add ruff.toml and CI lint step
```

Prefixes: `fix:`, `feat:`, `chore:`, `docs:`, `test:`.

## Adding a new executor

1. **Schema** — add the action type to `schemas/action.schema.json`:
   ```json
   "enum": ["research", "code", "browser", "message", "wait", "<new_type>"]
   ```

2. **Executor implementation** — add the new logic to the appropriate module under `agents/executors/` (for example `browser.py`, `code_executor.py`, or a new module if warranted) and re-export any public surface from `agents/executors/__init__.py`.

3. **Classifier** — update `agents/planner.py` `classify_text()` to route inputs to the new type.

4. **Role prompt** — create `prompts/executors/<name>.md` with role, inputs, output contract, and rules.

5. **Verification gate** — add `<name>` to `config/policies.yaml` `verification.required_for` if evidence is needed.

6. **Tests** — add tests in `tests/` covering the happy path and error cases.

7. **Docs** — update `README.md` executor status table and this file.

## Loop bootstrap

On first run (or after `python3 agents/loop.py init`), the following files are created automatically:

- `state/current_state.json` — latest condensed state
- `state/event_queue.json` — pending events awaiting a loop
- `state/open_loops.json` — tracked open loops with evidence
- `state/recent_changes.md` — latest research summaries

These are all excluded from source control (see `.gitignore`). Delete them to get a clean slate.

## File I/O conventions

All state writes go through `agents/store.py`:

- `read_json(path)` — read a JSON file
- `write_json(path, data)` — atomic write (temp file + rename)
- `append_json_array(path, item)` — read-modify-write with locking

Do not write to state files directly. Always use the store module.

## Schema validation

Schemas live in `schemas/` and are loaded at startup. If you add a field that breaks validation:

1. Update the relevant `.schema.json` file
2. Run `python3 -c "from agents.validate import validate_payload; print('ok')"`
3. Update affected tests

Schema registry is cached at module level — no need to manually invalidate.

## Running the loop manually

```bash
# One shot
python3 agents/loop.py

# Enqueue tasks first
python3 agents/loop.py enqueue "look into the auth regression"
python3 agents/loop.py enqueue "review recent commits"

# Interactive repl
python3 agents/loop.py repl
```

## Reporting issues

Use GitHub issues. For bugs, include:
- What you expected vs what happened
- Relevant log output or state files
- Steps to reproduce

For design questions, open an issue first before submitting PRs.

## Code review process

All changes go through PR. PRs require:
- `make test` passes
- `ruff check .` clean (no new violations)
- PR description links to the issue being addressed
