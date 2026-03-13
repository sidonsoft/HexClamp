# Project Brief

## What this is

Hydra-Claw-Loop is an inspectable autonomous agent loop scaffold that separates observation, condensation, planning, execution, verification, and persistence.

## Why it exists

To avoid prompt soup, reduce rediscovery, and make agent progress auditable and recoverable.

## Initial operating constraints

- Keep state file-backed.
- Prefer condensed context over full rescans.
- Require evidence for meaningful actions.
- Start with one executor vertical slice.

## Current phase

Draft scaffold and starter implementation.
