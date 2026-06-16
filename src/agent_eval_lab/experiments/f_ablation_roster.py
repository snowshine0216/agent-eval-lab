"""F-set ablation roster — the version-controlled source of truth for WHICH
models the ablation compares (§B.6).

Separated from the frozen methodology (f_ablation_spec: k, seed, the uniform
40-round cap, the 2×2 arms, metrics) so adding/removing a model is a config edit,
never a code change. I/O lives at the edge here (tomllib); build_f_ablation_spec
stays pure and takes the parsed conditions + experiment_id explicitly.

Provider validation is opt-in via an explicit `valid_providers` set (dependencies
visible in the signature — the CLI passes frozenset(PROVIDERS) so a typo'd
provider is caught before any paid run, while unit tests stay decoupled from the
provider registry).
"""

from __future__ import annotations

import tomllib
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from agent_eval_lab.experiments.schema import ConditionDef


@dataclass(frozen=True, kw_only=True)
class FAblationRoster:
    """The parsed roster: the experiment identity + the ordered conditions.

    Entry order is significant — it feeds the seeded ablation_run_order, so the
    realized execution order is reproducible from this file."""

    experiment_id: str
    conditions: tuple[ConditionDef, ...]


def load_f_ablation_roster(
    path: Path, *, valid_providers: Collection[str] | None = None
) -> FAblationRoster:
    """Load and validate an F-ablation roster TOML into a frozen FAblationRoster.

    Args:
        path: the roster TOML file.
        valid_providers: when given, every condition_id's provider half MUST be in
            this set (else ValueError) — the CLI passes the PROVIDERS registry so a
            typo never reaches a paid run. When None, provider names are not checked.

    Raises:
        FileNotFoundError: the path does not exist.
        ValueError: missing experiment_id; no [[model]] entries; a model entry
            missing condition_id/label; a condition_id that is not provider:model;
            or (with valid_providers) an unregistered provider.
    """
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    if "experiment_id" not in data:
        raise ValueError(f"{path} is missing required key 'experiment_id'")
    experiment_id = str(data["experiment_id"])

    models = data.get("model")
    if not models:
        raise ValueError(f"{path} must declare at least one [[model]] entry")

    conditions = tuple(_parse_model(entry, path, valid_providers) for entry in models)
    return FAblationRoster(experiment_id=experiment_id, conditions=conditions)


def _parse_model(
    entry: dict, path: Path, valid_providers: Collection[str] | None
) -> ConditionDef:
    if "condition_id" not in entry:
        raise ValueError(f"{path} [[model]] entry is missing 'condition_id'")
    if "label" not in entry:
        raise ValueError(f"{path} [[model]] entry is missing 'label'")
    condition_id = str(entry["condition_id"])
    provider, sep, model = condition_id.partition(":")
    if not sep or not provider or not model:
        raise ValueError(
            f"{path} condition_id {condition_id!r} must be 'provider:model'"
        )
    if valid_providers is not None and provider not in valid_providers:
        raise ValueError(
            f"{path} condition_id {condition_id!r} names unknown provider "
            f"{provider!r}; registered: {sorted(valid_providers)}"
        )
    return ConditionDef(condition_id=condition_id, label=str(entry["label"]))
