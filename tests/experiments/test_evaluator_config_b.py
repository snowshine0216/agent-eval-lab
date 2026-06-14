"""Config plumbing for the B-set extras ([candidate] + [oracle.b_set.goldens]).

Every value here is an OBVIOUSLY-FAKE placeholder written by the test into a
tmp TOML. NEVER read the real gitignored evaluator.toml — no real creds/ids in
a tracked file (public repo).
"""

from pathlib import Path

import pytest

from agent_eval_lab.experiments.evaluator_config import (
    CandidateConfig,
    load_evaluator_config,
)

_FIXTURE_TOML = """\
[store]
path = "/tmp/fake-store"

[health_probe]
url = "https://fake.example/auth"
username = "fake-user"
password = "fake-pass"

[skill]
strategy_test_path = "/tmp/fake-skill/SKILL.md"

[runner]
safety_cap = 200
k_valid = 5
max_invalid_rate = 0.4

[candidate]
url = "https://fake.example/MicroStrategyLibrary/app"
username = "fake-candidate"
password = "fake-candidate-pass"

[oracle.b_set]
readback = "playwright-cli"
project_id = "FAKE_PROJECT_ID"

[oracle.b_set.goldens]
"B-1" = "fake-golden-object-0001"
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "fixture-evaluator.toml"
    p.write_text(_FIXTURE_TOML, encoding="utf-8")
    return p


def test_loads_candidate_config(tmp_path: Path) -> None:
    cfg = load_evaluator_config(_write(tmp_path))
    assert isinstance(cfg.candidate, CandidateConfig)
    assert cfg.candidate.url.endswith("/MicroStrategyLibrary/app")
    assert cfg.candidate.username == "fake-candidate"
    assert cfg.candidate.password == "fake-candidate-pass"


def test_loads_oracle_b_set_project_and_goldens(tmp_path: Path) -> None:
    cfg = load_evaluator_config(_write(tmp_path))
    assert cfg.oracle_b_set.readback == "playwright-cli"
    assert cfg.oracle_b_set.project_id == "FAKE_PROJECT_ID"
    assert cfg.oracle_b_set.goldens == {"B-1": "fake-golden-object-0001"}


def test_missing_candidate_section_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace(
        '[candidate]\n'
        'url = "https://fake.example/MicroStrategyLibrary/app"\n'
        'username = "fake-candidate"\n'
        'password = "fake-candidate-pass"\n',
        "",
    )
    p = tmp_path / "no-candidate.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[candidate\]"):
        load_evaluator_config(p)


def test_missing_project_id_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace('project_id = "FAKE_PROJECT_ID"\n', "")
    p = tmp_path / "no-project.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match="project_id"):
        load_evaluator_config(p)


def test_missing_goldens_subtable_raises_clear_value_error(tmp_path: Path) -> None:
    toml = _FIXTURE_TOML.replace(
        '[oracle.b_set.goldens]\n"B-1" = "fake-golden-object-0001"\n', ""
    )
    p = tmp_path / "no-goldens.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[oracle\.b_set\.goldens\]"):
        load_evaluator_config(p)
