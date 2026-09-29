"""JSON-schema helpers for provider structured-output APIs."""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel

# Annotation keywords that some providers reject; stripped only where they act as keywords.
_ANNOTATION_KEYWORDS = frozenset({"title", "examples", "default"})
# Keywords whose value is a mapping of *names* (not keywords) to sub-schemas.
_NAME_MAPPINGS = frozenset({"properties", "patternProperties"})


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local `$ref`s into a self-contained schema (tool/response schemas dislike refs)."""
    definitions: dict[str, Any] = schema.get("$defs", {})

    def resolve_schema(node: Any, depth: int) -> Any:
        if depth > 40:
            raise ValueError("Schema nesting too deep (recursive model?)")
        if isinstance(node, list):
            return [resolve_schema(item, depth + 1) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = copy.deepcopy(definitions[ref.removeprefix("#/$defs/")])
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return resolve_schema(merged, depth + 1)
        result: dict[str, Any] = {}
        for key, value in node.items():
            if key == "$defs" or key in _ANNOTATION_KEYWORDS:
                continue
            if key in _NAME_MAPPINGS and isinstance(value, dict):
                result[key] = {name: resolve_schema(sub, depth + 1) for name, sub in value.items()}
            else:
                result[key] = resolve_schema(value, depth + 1)
        return result

    resolved: dict[str, Any] = resolve_schema(schema, 0)
    return resolved


def schema_for(model: type[BaseModel]) -> dict[str, Any]:
    return inline_refs(model.model_json_schema())
