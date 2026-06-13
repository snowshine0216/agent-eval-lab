"""Tests for the freeze-spec and check-env CLI subcommands.

check-env: mock playwright subprocess + httpx client — no real network or binary.
freeze-spec: round-trip through JSON; verify idempotency.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from agent_eval_lab.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _draft_spec_dict() -> dict:
    """A valid draft ExperimentSpec as a plain dict (JSON-serialisable)."""
    return {
        "experiment_id": "M1",
        "k": 3,
        "repeats": 1,
        "safety_cap": 12,
        "max_invalid_rate": 0.25,
        "conditions": [
            {"condition_id": "deepseek:deepseek-v4-pro", "label": "noskill",
             "skill_variant": "none", "system_prompt_hash": None}
        ],
        "metrics": [
            {
                "name": "pass_pow_k",
                "domain": "F",
                "primary": True,
                "aggregation": "pass_pow_k",
                "ci_method": "cluster_bootstrap",
                "validity_mask": True,
                "censoring_policy": "failure",
            }
        ],
        "macro_weights": [{"domain": "F", "weight": 1.0}],
        "families": [
            {"id": "main", "description": "d", "correction": "holm", "alpha": 0.05}
        ],
        "planned_comparisons": [],
        "dataset_snapshot_hash": "aabbcc",
        "pricing_snapshot_hash": "ddeeff",
        "spec_hash": "",
    }


# ---------- freeze-spec ----------

def test_freeze_spec_writes_frozen_json(tmp_path: Path) -> None:
    draft_path = tmp_path / "draft.json"
    out_path = tmp_path / "frozen.json"
    draft_path.write_text(json.dumps(_draft_spec_dict()))
    rc = main(["freeze-spec", "--spec", str(draft_path), "--out", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert len(data["spec_hash"]) == 64


def test_freeze_spec_prints_hash(tmp_path: Path, capsys) -> None:
    draft_path = tmp_path / "draft.json"
    out_path = tmp_path / "frozen.json"
    draft_path.write_text(json.dumps(_draft_spec_dict()))
    main(["freeze-spec", "--spec", str(draft_path), "--out", str(out_path)])
    captured = capsys.readouterr()
    printed = captured.out.strip()
    assert len(printed) == 64  # SHA256 hex


def test_freeze_spec_idempotent(tmp_path: Path) -> None:
    """Running freeze-spec twice on the same draft yields the same hash."""
    draft_path = tmp_path / "draft.json"
    out_path = tmp_path / "frozen.json"
    draft_path.write_text(json.dumps(_draft_spec_dict()))
    main(["freeze-spec", "--spec", str(draft_path), "--out", str(out_path)])
    frozen_data = json.loads(out_path.read_text())
    hash1 = frozen_data["spec_hash"]

    # Run again using the frozen output as input
    main(["freeze-spec", "--spec", str(out_path), "--out", str(out_path)])
    frozen_data2 = json.loads(out_path.read_text())
    assert frozen_data2["spec_hash"] == hash1


def test_freeze_spec_invalid_spec_exits_nonzero(tmp_path: Path) -> None:
    """A spec with empty conditions must exit non-zero (validation error)."""
    bad = _draft_spec_dict()
    bad["conditions"] = []
    bad["metrics"] = []
    draft_path = tmp_path / "bad.json"
    out_path = tmp_path / "out.json"
    draft_path.write_text(json.dumps(bad))
    rc = main(["freeze-spec", "--spec", str(draft_path), "--out", str(out_path)])
    assert rc != 0


# ---------- check-env: playwright ----------

def _make_completed_process(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["playwright-cli", "--version"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_check_env_playwright_ok_no_config(capsys) -> None:
    version_str = "playwright-cli 1.2.3\n"
    with patch("subprocess.run", return_value=_make_completed_process(0, version_str)):
        rc = main(["check-env"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok]" in out
    assert "playwright-cli" in out.lower()


def test_check_env_playwright_missing_exits_1(capsys) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        rc = main(["check-env"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out


def test_check_env_playwright_nonzero_exit_fails(capsys) -> None:
    proc = _make_completed_process(1, stderr="not found")
    with patch("subprocess.run", return_value=proc):
        rc = main(["check-env"])
    assert rc == 1


def test_check_env_skips_probe_when_no_config(capsys) -> None:
    with patch("subprocess.run", return_value=_make_completed_process(0, "v1\n")):
        main(["check-env"])
    out = capsys.readouterr().out
    assert "[skip]" in out or "MSTR" in out


# ---------- check-env: MSTR health probe ----------

def _ok_client() -> httpx.Client:
    """A mock httpx.Client that returns 200 for any request."""
    mock = MagicMock(spec=httpx.Client)
    mock.post.return_value = httpx.Response(200)
    return mock


def _fail_client(status: int) -> httpx.Client:
    mock = MagicMock(spec=httpx.Client)
    mock.post.return_value = httpx.Response(status)
    return mock


def test_check_env_probe_ok_with_config(tmp_path: Path, capsys) -> None:
    with patch("subprocess.run", return_value=_make_completed_process(0, "v1\n")):
        rc = main(
            ["check-env", "--evaluator-config", str(FIXTURES / "evaluator.toml")],
            http_client=_ok_client(),
        )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok]" in out


def test_check_env_probe_fail_4xx_exits_1(tmp_path: Path, capsys) -> None:
    with patch("subprocess.run", return_value=_make_completed_process(0, "v1\n")):
        rc = main(
            ["check-env", "--evaluator-config", str(FIXTURES / "evaluator.toml")],
            http_client=_fail_client(401),
        )
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out


def test_check_env_probe_2xx_and_3xx_are_healthy(tmp_path: Path, capsys) -> None:
    """2XX and 3XX responses are both treated as healthy (§18.5)."""
    for status in (200, 201, 302):
        with patch("subprocess.run", return_value=_make_completed_process(0, "v1\n")):
            rc = main(
                ["check-env", "--evaluator-config", str(FIXTURES / "evaluator.toml")],
                http_client=_fail_client(status),
            )
        assert rc == 0, f"Expected 0 for HTTP {status}"


def test_check_env_missing_config_file_exits_1(tmp_path: Path, capsys) -> None:
    with patch("subprocess.run", return_value=_make_completed_process(0, "v1\n")):
        rc = main(
            ["check-env", "--evaluator-config", "/nonexistent/evaluator.toml"],
            http_client=_ok_client(),
        )
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out


# ---------- health_probe function (factored, reusable) ----------

def test_health_probe_function_returns_healthy_on_2xx() -> None:
    """The standalone health_probe function must be importable and testable."""
    from agent_eval_lab.experiments.evaluator_config import health_probe

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = httpx.Response(200)
    result = health_probe(
        url="http://example.com/api/auth/login",
        username="user",
        password="pass",
        client=mock_client,
    )
    assert result.healthy is True
    assert result.status_code == 200


def test_health_probe_function_returns_unhealthy_on_4xx() -> None:
    from agent_eval_lab.experiments.evaluator_config import health_probe

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = httpx.Response(401)
    result = health_probe(
        url="http://example.com/api/auth/login",
        username="user",
        password="pass",
        client=mock_client,
    )
    assert result.healthy is False
    assert result.status_code == 401


def test_health_probe_treats_3xx_as_healthy() -> None:
    from agent_eval_lab.experiments.evaluator_config import health_probe

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = httpx.Response(302)
    result = health_probe(
        url="http://example.com/api/auth/login",
        username="user",
        password="pass",
        client=mock_client,
    )
    assert result.healthy is True
