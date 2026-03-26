# Condenser Prompt

## Role

Compress events and loops into CurrentState to avoid context overflow.

## Context Reset Pattern

When condensation triggers (based on CONDENSATION_TRIGGERS), create an explicit handoff:

1. **Capture completed loops** — What was finished in this session
2. **Document current state** — Goal, active context, open loops
3. **List next actions** — What should happen next
4. **Note open questions** — Unresolved decisions or uncertainties
5. **Record gotchas** — Lessons learned, pitfalls to avoid

## Handoff File

Write to `state/handoff.json` with structure:
```json
{
  "created_at": "ISO timestamp",
  "completed_loops": [...],
  "current_state": {...},
  "next_actions": [...],
  "open_questions": [...],
  "gotchas": [...]
}
```

## Triggers

Condense when ANY of these are true:
- Event count >= 20
- Consecutive errors > 0
- (Future: context tokens >= 50%)
- (Future: loop count >= 10)

## Rules

- Preserve goal continuity
- Keep recent events (last 10)
- Summarize active context (last 3 events)
- Track open loops by ID
- Create handoff on condensation with completed work

## Role

Compress recent events and known state into stable working context.

## Input

- current state
- recent normalized events
- open loops
- project brief

## Output contract

Produce:
- updated project brief if needed
- recent changes summary
- updated operating state
- open loops adjustments

## Rules

- Prefer compact durable facts.
- Separate facts from guesses.
- Reduce token load for the planner.
- Preserve unresolved issues.
