---
title: Schemas
description: HexClamp JSON Schema reference
---

# JSON Schemas

HexClamp uses JSON Schema for validation of all state files. Schemas are stored in `schemas/` and validated at load time via `agents/validate.py` with caching.

Schemas are the **source of truth** for the structure of events, actions, loops, results, and state.

---

## Schema Overview

| Schema | File | Validates |
|--------|------|-----------|
| Event | `schemas/event.schema.json` | Individual `Event` objects |
| Action | `schemas/action.schema.json` | `Action` objects and action arrays |
| Loop | `schemas/loop.schema.json` | `OpenLoop` objects and open loops arrays |
| Result | `schemas/result.schema.json` | `Result` objects |
| State | `schemas/state.schema.json` | `CurrentState` objects |
| Event Queue | `event-queue.schema.json` | Array of Event objects |
| Open Loops | `open-loops.schema.json` | Array of OpenLoop objects |

---

## `event.schema.json`

Defines the structure of an `Event`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "timestamp", "source", "kind", "payload", "tags", "priority"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^evt_"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "source": {
      "type": "string",
      "enum": ["cli", "telegram", "poll", "system"]
    },
    "kind": {
      "type": "string"
    },
    "payload": {
      "type": "object"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "priority": {
      "type": "string",
      "enum": ["normal", "high"]
    }
  }
}
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Must start with `evt_` |
| `timestamp` | ISO 8601 datetime | When the event was created |
| `source` | enum | Origin of the event |
| `kind` | string | Event type |
| `payload` | object | Normalised content (e.g., `{"text": "..."}`) |
| `tags` | string[] | Extracted labels |
| `priority` | enum | `normal` or `high` |

---

## `action.schema.json`

Defines the structure of an `Action`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "type", "goal", "inputs", "executor", "success_criteria", "risk", "status"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^act_"
    },
    "type": {
      "type": "string",
      "enum": ["research", "code", "browser", "messaging"]
    },
    "goal": {
      "type": "string"
    },
    "inputs": {
      "type": "array",
      "items": { "type": "string" }
    },
    "executor": {
      "type": "string"
    },
    "success_criteria": {
      "type": "string"
    },
    "risk": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "status": {
      "type": "string",
      "enum": ["planned", "running", "done", "failed"]
    }
  }
}
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Must start with `act_` |
| `type` | enum | Executor action type |
| `goal` | string | What the action aims to achieve |
| `inputs` | string[] | Input references |
| `executor` | string | Which executor runs this |
| `success_criteria` | string | Definition of done |
| `risk` | enum | Risk level |
| `status` | enum | Current status |

---

## `loop.schema.json`

Defines the structure of an `OpenLoop`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "title", "status", "priority", "owner", "created_at", "updated_at", "next_step"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^loop_"
    },
    "title": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["open", "blocked", "resolved"]
    },
    "priority": {
      "type": "string",
      "enum": ["low", "normal", "high", "urgent"]
    },
    "owner": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    },
    "next_step": {
      "type": "string"
    },
    "blocked_by": {
      "type": "array",
      "items": { "type": "string" }
    },
    "evidence": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Must start with `loop_` |
| `title` | string | Human-readable task title |
| `status` | enum | `open`, `blocked`, or `resolved` |
| `priority` | enum | Task priority |
| `owner` | string | Owner/agent responsible |
| `blocked_by` | string[] | IDs of blocking loops |
| `evidence` | string[] | Proof items collected |

---

## `result.schema.json`

Defines the structure of a `Result`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["action_id", "status", "summary"],
  "properties": {
    "action_id": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["success", "partial", "failed"]
    },
    "summary": {
      "type": "string"
    },
    "evidence": {
      "type": "array",
      "items": { "type": "string" }
    },
    "artifacts": {
      "type": "array",
      "items": { "type": "string" }
    },
    "follow_up": {
      "type": "array",
      "items": { "type": "string" }
    },
    "verified": {
      "type": "boolean"
    }
  }
}
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | string | Reference to the action that produced this result |
| `status` | enum | `success`, `partial`, or `failed` |
| `summary` | string | Human-readable outcome |
| `evidence` | string[] | Proof items (file paths, URLs, status strings) |
| `artifacts` | string[] | Files produced |
| `verified` | boolean | Set by the verifier |

---

## `state.schema.json`

Defines the structure of `CurrentState`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["goal"],
  "properties": {
    "goal": {
      "type": "string"
    },
    "active_context": {
      "type": "array",
      "items": { "type": "string" }
    },
    "recent_events": {
      "type": "array",
      "items": { "type": "string" }
    },
    "current_actions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "open_loops": {
      "type": "array",
      "items": { "type": "string" }
    },
    "last_verified_result": {
      "type": ["object", "null"]
    }
  }
}
```

---

## Validation in Code

Schemas are validated automatically when state files are loaded:

```python
from agents.validate import validate_payload

# Validate a single event
validate_payload(item, "event.schema.json")

# Validate an array
validate_payload(items, "event-queue.schema.json")
```

The validator caches loaded schemas for the lifetime of the process to avoid repeated file I/O.

---

## Adding a New Schema

1. Create `schemas/<name>.schema.json` following JSON Schema Draft-07
2. Register validation calls in `agents/validate.py`
3. Update `agents/models.py` if adding a new dataclass
4. Update this documentation
