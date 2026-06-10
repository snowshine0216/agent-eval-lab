"""Shared JSON-Schema argument validation (the world and graders agree)."""

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator


def validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> str | None:
    """Return None when args satisfy schema, else a human-readable error."""
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(dict(args)), key=lambda e: list(e.absolute_path)
    )
    if not errors:
        return None
    first = errors[0]
    path = ".".join(str(p) for p in first.absolute_path) or "<root>"
    return f"{path}: {first.message}"
