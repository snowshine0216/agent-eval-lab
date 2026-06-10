"""Value-preserving canonicalization for comparing and serializing arguments.

Only proven-equivalent forms are normalized (mapping key order; sequence type).
Type coercion is NEVER performed here — `"1"` and `1` stay distinct; the
schema validator decides whether a value is legal.
"""

from collections.abc import Mapping
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return tuple(canonicalize(item) for item in value)
    return value
