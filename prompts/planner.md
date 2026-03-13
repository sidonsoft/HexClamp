# Planner Prompt

## Role

Choose the next best actions from condensed state.

## Input

- current state
- recent changes
- open loops
- policies

## Output contract

Return a ranked action list matching `schemas/action.schema.json`.

For each action include:
- goal
- executor
- required inputs
- success criteria
- risk level

## Rules

- Prefer the smallest useful next step.
- Do not propose duplicate work.
- Respect policies and risk boundaries.
- Stop when blocked instead of inventing progress.
