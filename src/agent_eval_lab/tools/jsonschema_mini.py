"""Minimal, dependency-free JSON-Schema validator (subset).

Supports: type (object/string/integer/number/boolean/array), properties,
required, enum, additionalProperties:false. Returns a list of human-readable
error strings; [] means valid. NEVER coerces types ("1" != integer).
Applied identically at the tool-world boundary and the AST grader.
"""

from typing import Any

_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list, tuple),
    "object": (dict,),
}


def _type_ok(value: Any, expected: str) -> bool:
    # bool is a subclass of int in Python; exclude it from numeric types.
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _PY_TYPES[expected])


def validate(instance: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Validate instance against schema. Returns error messages; [] if valid."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _type_ok(instance, expected):
        errors.append(f"{path or '<root>'}: expected type {expected}")
        return errors
    if expected == "object":
        errors.extend(_validate_object(instance, schema, path))
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path or '<root>'}: {instance!r} not in enum {schema['enum']}")
    return errors


def _validate_object(instance: dict, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    props: dict[str, Any] = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in instance:
            errors.append(f"{path}{name}: required property missing")
    if schema.get("additionalProperties") is False:
        for key in instance:
            if key not in props:
                errors.append(f"{path}{key}: additional property not allowed")
    for key, value in instance.items():
        if key in props:
            errors.extend(validate(value, props[key], f"{path}{key}."))
    return errors
