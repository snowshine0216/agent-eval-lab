"""Evaluator configuration — typed evaluator.toml loader (§18.4).

Uses tomllib (Python 3.11 stdlib). Frozen dataclasses throughout.
The health_probe function is factored here so item 006 can import it directly.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config dataclasses (frozen)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class StoreConfig:
    path: str


@dataclass(frozen=True, kw_only=True)
class HealthProbeConfig:
    url: str
    username: str
    password: str


@dataclass(frozen=True, kw_only=True)
class SkillConfig:
    strategy_test_path: str


@dataclass(frozen=True, kw_only=True)
class CandidateConfig:
    """The least-privilege candidate MSTR account (D20). Distinct from the
    evaluator account used by health_probe / the readback oracle; this account
    CANNOT read the golden (D19/D33)."""

    url: str
    username: str
    password: str


@dataclass(frozen=True, kw_only=True)
class RunnerConfig:
    safety_cap: int
    k_valid: int
    max_invalid_rate: float


@dataclass(frozen=True, kw_only=True)
class OracleBSetConfig:
    readback: str  # readback strategy, e.g. "playwright-cli" (§18.4/§18.7)
    project_id: str  # MSTR project the run folder + golden live in (§18.7)
    goldens: Mapping[str, str]  # task-id -> golden object id (evaluator-only, D19)


@dataclass(frozen=True, kw_only=True)
class EvaluatorConfig:
    store: StoreConfig
    health_probe: HealthProbeConfig
    skill: SkillConfig
    candidate: CandidateConfig
    runner: RunnerConfig
    oracle_b_set: OracleBSetConfig


# ---------------------------------------------------------------------------
# health_probe — factored for reuse by item 006
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ProbeResult:
    """Result of a single health probe attempt."""

    healthy: bool
    status_code: int | None


def health_probe(
    url: str,
    username: str,
    password: str,
    *,
    client: httpx.Client,
) -> ProbeResult:
    """POST to the MSTR auth endpoint; treat 2XX/3XX as healthy (§18.5).

    Pure I/O wrapper — all decision logic (threshold < 400) is inline so
    item 006 can call this function without reimplementing it.
    """
    resp = client.post(
        url,
        json={"username": username, "password": password, "loginMode": 1},
        headers={"accept": "application/json", "Content-Type": "application/json"},
    )
    return ProbeResult(healthy=resp.status_code < 400, status_code=resp.status_code)


# ---------------------------------------------------------------------------
# load_evaluator_config — I/O at the edge
# ---------------------------------------------------------------------------


def _require_section(data: dict, section: str) -> dict:
    """Return a required TOML section or raise ValueError with a clear message."""
    if section not in data:
        raise ValueError(f"evaluator.toml is missing required section [{section}]")
    return data[section]


def _require_key(section: dict, key: str, section_name: str) -> object:
    if key not in section:
        raise ValueError(
            f"evaluator.toml [{section_name}] is missing required key '{key}'"
        )
    return section[key]


def load_evaluator_config(path: Path) -> EvaluatorConfig:
    """Load and validate evaluator.toml, returning a frozen EvaluatorConfig.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if a required section or key is absent.
    """
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    store_sec = _require_section(data, "store")
    hp_sec = _require_section(data, "health_probe")
    skill_sec = _require_section(data, "skill")
    candidate_sec = _require_section(data, "candidate")
    runner_sec = _require_section(data, "runner")
    # §18.4 declares a NESTED table [oracle.b_set]; tomllib parses it as
    # data["oracle"]["b_set"]. Read it that way (not a flat [oracle_b_set]).
    oracle_parent = _require_section(data, "oracle")
    if "b_set" not in oracle_parent:
        raise ValueError("evaluator.toml is missing required section [oracle.b_set]")
    oracle_sec = oracle_parent["b_set"]
    if "goldens" not in oracle_sec:
        raise ValueError(
            "evaluator.toml is missing required section [oracle.b_set.goldens]"
        )
    goldens_sec = oracle_sec["goldens"]

    return EvaluatorConfig(
        store=StoreConfig(
            path=str(_require_key(store_sec, "path", "store")),
        ),
        health_probe=HealthProbeConfig(
            url=str(_require_key(hp_sec, "url", "health_probe")),
            username=str(_require_key(hp_sec, "username", "health_probe")),
            password=str(_require_key(hp_sec, "password", "health_probe")),
        ),
        skill=SkillConfig(
            strategy_test_path=str(
                _require_key(skill_sec, "strategy_test_path", "skill")
            ),
        ),
        candidate=CandidateConfig(
            url=str(_require_key(candidate_sec, "url", "candidate")),
            username=str(_require_key(candidate_sec, "username", "candidate")),
            password=str(_require_key(candidate_sec, "password", "candidate")),
        ),
        runner=RunnerConfig(
            safety_cap=int(_require_key(runner_sec, "safety_cap", "runner")),
            k_valid=int(_require_key(runner_sec, "k_valid", "runner")),
            max_invalid_rate=float(
                _require_key(runner_sec, "max_invalid_rate", "runner")
            ),
        ),
        oracle_b_set=OracleBSetConfig(
            readback=str(_require_key(oracle_sec, "readback", "oracle.b_set")),
            project_id=str(_require_key(oracle_sec, "project_id", "oracle.b_set")),
            goldens={str(k): str(v) for k, v in goldens_sec.items()},
        ),
    )
