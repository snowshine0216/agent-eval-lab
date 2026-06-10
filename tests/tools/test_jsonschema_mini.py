from agent_eval_lab.tools.jsonschema_mini import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "count": {"type": "integer"},
    },
    "required": ["title", "priority"],
    "additionalProperties": False,
}


def test_valid_object_returns_no_errors():
    assert validate({"title": "x", "priority": "low"}, SCHEMA) == []


def test_missing_required_field_reported():
    errs = validate({"title": "x"}, SCHEMA)
    assert any("priority" in e for e in errs)


def test_wrong_type_reported_no_coercion():
    # "1" where integer required must FAIL — never coerced.
    errs = validate({"title": "x", "priority": "low", "count": "1"}, SCHEMA)
    assert any("count" in e for e in errs)


def test_bool_is_not_integer():
    errs = validate({"title": "x", "priority": "low", "count": True}, SCHEMA)
    assert any("count" in e for e in errs)


def test_enum_violation_reported():
    errs = validate({"title": "x", "priority": "urgent"}, SCHEMA)
    assert any("priority" in e for e in errs)


def test_additional_property_reported():
    errs = validate({"title": "x", "priority": "low", "extra": 1}, SCHEMA)
    assert any("extra" in e for e in errs)


def test_non_object_top_level_reported():
    errs = validate(["not", "an", "object"], SCHEMA)
    assert errs != []
