import argparse
import json
from pathlib import Path

from agent_eval_lab.records.trajectory import (
    PROVIDER_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)


def _ok(run_index):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
        run_index=run_index,
        stop_reason="completed_natural",
        rounds=5,
        wall_time_s=8.0,
    )


def _write_cfg(tmp_path: Path) -> Path:
    toml = tmp_path / "evaluator.toml"
    toml.write_text(
        """
[store]
path = "{store}"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "{skill}"
[candidate]
url = "https://lab/app"
username = "bxu"
password = "secret"
folder = "/Candidate/bxu"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""".format(store=tmp_path / "store", skill=tmp_path / "skill.md"),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# stripped skill\n", encoding="utf-8")
    return toml


def test_run_b_writes_trials_and_verdict_sheet_both_arms(tmp_path, monkeypatch) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    # The candidate factory returns a fake run_fn (no provider, no MSTR).
    def fake_factory(*, arm, condition_id, folder, login):
        def run_fn(task, run_index, save_name):
            return _ok(run_index)

        return run_fn

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0

    # One trials artifact per arm (task_id), BTrial JSONL (no "grade" key).
    noskill = list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    skill = list(out.glob("trials-b-*-b-b1-skill.jsonl"))
    assert len(noskill) == 1 and len(skill) == 1
    line = json.loads(noskill[0].read_text().splitlines()[0])
    assert "grade" not in line
    assert line["save_name"].endswith("__b-b1-noskill__0000")
    # A void sidecar + the verdict sheet (md + csv) exist.
    assert (noskill[0].with_suffix(".void.json")).exists()
    assert list(out.glob("b1-verdict-sheet-*.md"))
    assert list(out.glob("b1-verdict-sheet-*.csv"))


def test_run_b_single_arm(tmp_path) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    def fake_factory(*, arm, condition_id, folder, login):
        return lambda task, run_index, save_name: _ok(run_index)

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="noskill",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0
    assert list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    assert not list(out.glob("trials-b-*-b-b1-skill.jsonl"))


def _write_cfg_missing_folder(tmp_path: Path) -> Path:
    """Config with [candidate] folder omitted (required for a live run)."""
    toml = tmp_path / "evaluator-no-folder.toml"
    toml.write_text(
        """
[store]
path = "{store}"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "{skill}"
[candidate]
url = "https://lab/app"
username = "bxu"
password = "secret"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""".format(store=tmp_path / "store", skill=tmp_path / "skill.md"),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# stripped skill\n", encoding="utf-8")
    return toml


def test_run_b_missing_candidate_folder_returns_nonzero_and_never_calls_factory(
    tmp_path,
) -> None:
    """P0-2: a config missing [candidate] folder must fail-fast (rc=2) before any
    trial runs. The fake factory must never be called when config is invalid."""
    from agent_eval_lab import cli

    cfg = _write_cfg_missing_folder(tmp_path)
    out = tmp_path / "out"

    factory_calls: list = []

    def fake_factory(*, arm, condition_id, folder, login):
        factory_calls.append(arm)
        return lambda task, run_index, save_name: _ok(run_index)

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc != 0  # config error → nonzero
    assert factory_calls == []  # factory was never called
    # No trials artifacts should have been written
    assert not list(out.glob("trials-b-*.jsonl")) if out.exists() else True


def test_run_b_missing_storage_state_file_fails_fast_and_never_calls_factory(
    tmp_path,
) -> None:
    """A [candidate] storage_state pointing at a non-existent file must fail-fast
    (rc=2) before any trial runs. Otherwise the candidate silently opens
    UNauthenticated, lands on the MSTR login page, and every trial censors —
    miscounted as a model FAIL instead of a setup error (ADR-0022; the §7 store
    relocation makes a stale/moved path very plausible)."""
    from agent_eval_lab import cli

    toml = tmp_path / "evaluator-bad-ss.toml"
    toml.write_text(
        """
[store]
path = "{store}"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "{skill}"
[candidate]
url = "https://lab/app"
username = "bxu"
password = "secret"
folder = "/Candidate/bxu"
storage_state = "{missing}"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""".format(
            store=tmp_path / "store",
            skill=tmp_path / "skill.md",
            missing=tmp_path / "does-not-exist" / "bxu-auth.json",
        ),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# stripped skill\n", encoding="utf-8")
    out = tmp_path / "out"

    factory_calls: list = []

    def fake_factory(*, arm, condition_id, folder, login):
        factory_calls.append(arm)
        return lambda task, run_index, save_name: _ok(run_index)

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=toml,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc != 0
    assert factory_calls == []
    assert not list(out.glob("trials-b-*.jsonl")) if out.exists() else True


def _provider_auth_traj(run_index):
    """A trajectory that provider_auth_quota_status recognises as a 403 block."""
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(
            raw='HTTP 403: {"code":"AllocationQuota.FreeTierOnly"}',
            error=PROVIDER_ERROR,
        ),
    )


def test_run_b_provider_auth_403_aborts_and_emits_verdict_sheet(tmp_path) -> None:
    """P1-3: a candidate run_fn returning a 403 provider-auth trajectory must make
    _run_b_command return rc=1, abort before the second arm runs, and still emit
    the verdict sheet (for whatever trials were recorded)."""
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    arms_called: list[str] = []

    def fake_factory(*, arm, condition_id, folder, login):
        def run_fn(task, run_index, save_name):
            arms_called.append(arm)
            return _provider_auth_traj(run_index)

        return run_fn

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 1  # auth/quota block → rc 1
    # The second arm ("skill") was never started — aborted after the first 403.
    assert "skill" not in arms_called
    # Verdict sheet is still written (even on abort, spec demands it).
    assert list(out.glob("b1-verdict-sheet-*.md"))
    assert list(out.glob("b1-verdict-sheet-*.csv"))
