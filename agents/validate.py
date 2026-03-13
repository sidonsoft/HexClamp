from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from store import SCHEMAS_DIR


def _build_registry() -> Registry:
    resources: dict[str, Resource[Any]] = {}
    for path in SCHEMAS_DIR.glob("*.json"):
        contents = json.loads(path.read_text(encoding="utf-8"))
        uri = path.resolve().as_uri()
        resources[uri] = Resource.from_contents(contents)
    return Registry().with_resources(resources.items())


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
