from __future__ import annotations

TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


def validate(data, schema, path="$") -> list:
    """Tiny schema checker. Schema forms: "string"|"integer"|"number"|"boolean", [elem], {field: schema}.
    Returns a list of problems (empty = valid). null is always allowed (= not found on the page)."""
    if data is None:
        return []
    if isinstance(schema, str):
        t = TYPES.get(schema)
        if t is None:
            return [f"{path}: unknown type {schema!r}"]
        if schema in ("integer", "number") and isinstance(data, bool):
            return [f"{path}: expected {schema}"]
        return [] if isinstance(data, t) else [f"{path}: expected {schema}, got {type(data).__name__}"]
    if isinstance(schema, list):
        if not isinstance(data, list):
            return [f"{path}: expected list"]
        return [p for i, x in enumerate(data) for p in validate(x, schema[0], f"{path}[{i}]")]
    if isinstance(schema, dict):
        if not isinstance(data, dict):
            return [f"{path}: expected object"]
        return [p for k, s in schema.items() for p in validate(data.get(k), s, f"{path}.{k}")]
    return [f"{path}: bad schema"]
