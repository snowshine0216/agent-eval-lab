import dataclasses

import pytest

from agent_eval_lab.records.env_health import EnvHealth


def test_env_health_is_frozen_and_total() -> None:
    h = EnvHealth(pre_healthy=True, post_healthy=False, pre_status=200, post_status=503)
    assert h.pre_healthy is True
    assert h.post_healthy is False
    assert h.pre_status == 200
    assert h.post_status == 503
    with pytest.raises(dataclasses.FrozenInstanceError):
        h.pre_healthy = False  # type: ignore[misc]


def test_env_health_status_fields_are_nullable() -> None:
    h = EnvHealth(
        pre_healthy=True, post_healthy=True, pre_status=None, post_status=None
    )
    assert h.pre_status is None
    assert h.post_status is None


def test_env_health_equality_is_structural() -> None:
    a = EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200)
    b = EnvHealth(pre_healthy=True, post_healthy=True, pre_status=200, post_status=200)
    assert a == b
