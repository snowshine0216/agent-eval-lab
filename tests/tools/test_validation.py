from agent_eval_lab.tools.validation import validate_args

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["title", "priority"],
    "additionalProperties": False,
}


def test_valid_args_return_none() -> None:
    assert validate_args(SCHEMA, {"title": "x", "priority": "low"}) is None


def test_missing_required_field_is_reported() -> None:
    error = validate_args(SCHEMA, {"title": "x"})

    assert error is not None
    assert "priority" in error


def test_wrong_type_is_never_coerced() -> None:
    error = validate_args(SCHEMA, {"title": "x", "priority": 1})

    assert error is not None
    assert "priority" in error


def test_enum_violation_is_reported() -> None:
    assert validate_args(SCHEMA, {"title": "x", "priority": "urgent"}) is not None


def test_additional_properties_are_rejected() -> None:
    error = validate_args(SCHEMA, {"title": "x", "priority": "low", "extra": 1})

    assert error is not None
