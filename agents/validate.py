from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from agents.store import SCHEMAS_DIR


# Module-level cache for schema registry (loaded once, reused across calls)
_registry_cache: Registry | None = None


def _build_registry() -> Registry:
    """Build the schema registry once and cache it."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    resources: dict[str, Resource[Any]] = {}
    for path in SCHEMAS_DIR.glob("*.json"):
        contents = json.loads(path.read_text(encoding="utf-8"))
        uri = path.resolve().as_uri()
        resources[uri] = Resource.from_contents(contents)
    _registry_cache = Registry().with_resources(resources.items())
    return _registry_cache


def load_schema(name: str) -> tuple[dict[str, Any], Registry]:
    path = SCHEMAS_DIR / name
    schema = json.loads(path.read_text(encoding="utf-8"))

    def rewrite_refs(value: Any) -> Any:
        if isinstance(value, dict):
            updated = {}
            for key, item in value.items():
                if key == "$ref" and isinstance(item, str) and item.startswith("./"):
                    updated[key] = (SCHEMAS_DIR / item[2:]).resolve().as_uri()
                else:
                    updated[key] = rewrite_refs(item)
            return updated
        if isinstance(value, list):
            return [rewrite_refs(item) for item in value]
        return value

    return rewrite_refs(schema), _build_registry()


def validate_payload(payload: Any, schema_name: str) -> None:
    schema, registry = load_schema(schema_name)
    validator = Draft202012Validator(schema, registry=registry)
    validator.validate(payload)
