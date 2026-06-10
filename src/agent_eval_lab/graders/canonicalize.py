"""Value-preserving, idempotent canonicalization for structural comparison.

Produces a hashable, order-normalized, type-tagged form so that True != 1 and
"1" != 1. Strictly value-preserving: never coerces or drops information.

Idempotence is a true fixed point: the output is a tagged tuple
``(tag, payload)`` whose first element is a known tag; re-applying canonicalize
to an already-canonical value returns it unchanged. This is required by spec A4
(``canonicalize(canonicalize(x)) == canonicalize(x)``) and lets canonical forms
be used directly as ``Counter`` keys in the multiset grader.

Domain note: inputs come from JSON (deserialized tool arguments), so they are
only dict / list / str / int / float / bool / None — never tuples. The only
tuples canonicalize ever sees are its own outputs, so the ``_is_canonical``
fixed-point guard is safe.
"""

from typing import Any

_TAGS = frozenset({"bool", "int", "float", "str", "NoneType", "dict", "list"})


def _is_canonical(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and value[0] in _TAGS
    )


def canonicalize(value: Any) -> Any:
    """Return a hashable, order-normalized, type-tagged form of value (idempotent)."""
    if _is_canonical(value):
        return value
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float, str)) or value is None:
        return (type(value).__name__, value)
    if isinstance(value, dict):
        return ("dict", tuple(sorted((k, canonicalize(v)) for k, v in value.items())))
    if isinstance(value, (list, tuple)):
        return ("list", tuple(canonicalize(v) for v in value))
    raise TypeError(f"cannot canonicalize {type(value).__name__}")
