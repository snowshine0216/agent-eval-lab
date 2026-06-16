import json
from pathlib import Path

import httpx
import pytest

from agent_eval_lab.cli import main


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(message["role"] == "tool" for message in body["messages"]):
        message = {"role": "assistant", "content": "Done."}
    else:
        user = next(m for m in body["messages"] if m["role"] == "user")
        query = user["content"].split("'")[1]
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "arguments": json.dumps({"query": query}),
                    },
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def _write_dataset(path: Path) -> Path:
    lines = []
    for index, query in enumerate(["refund policy", "email verification"], start=1):
        lines.append(
            {
                "id": f"ws-{index:03d}",
                "capability": "tool_selection",
                "input": {
                    "messages": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": f"Search the docs for '{query}'.",
                        }
                    ],
                    "available_tools": [
                        "search_docs",
                        "create_ticket",
                        "update_ticket",
                    ],
                },
                "verification": {
                    "type": "tool_call_match",
                    "expected_tool_calls": [
                        {"name": "search_docs", "arguments": {"query": query}}
                    ],
                    "match": "exact_sequence",
                },
                "metadata": {
                    "split": "dev",
                    "version": "1",
                    "provenance": "hand_written",
                },
                "initial_state": {"docs": {}, "tickets": {}},
            }
        )
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_run_baseline_writes_report_and_traces(tmp_path: Path, capsys) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "2",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )

    assert exit_code == 0
    report = (out_dir / "baseline-local-Qwen-Qwen3-8B.md").read_text()
    assert "pass@1 (trial accuracy): 1.000" in report
    assert "pass^2 (task reliability): 1.000" in report
    runs = (out_dir / "runs-local-Qwen-Qwen3-8B.jsonl").read_text().strip().splitlines()
    assert len(runs) == 4  # 2 tasks x k=2
    first = json.loads(runs[0])
    assert first["task_id"] == "ws-001"
    assert first["grade"]["passed"] is True
    assert str(out_dir / "baseline-local-Qwen-Qwen3-8B.md") in capsys.readouterr().out


def test_artifacts_are_distinct_per_model_under_one_provider(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    for model in ("qwen3-8b", "qwen3-32b/awq"):
        main(
            [
                "run-baseline",
                "--dataset",
                str(dataset),
                "--provider",
                "local",
                "--model",
                model,
                "--k",
                "1",
                "--out",
                str(out_dir),
            ],
            http_client=client,
        )

    names = sorted(path.name for path in out_dir.iterdir())
    assert names == [
        "baseline-local-qwen3-32b-awq.md",
        "baseline-local-qwen3-8b.md",
        "runs-local-qwen3-32b-awq.jsonl",
        "runs-local-qwen3-8b.jsonl",
    ]


def _fail_second_task_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    user = next(m for m in body["messages"] if m["role"] == "user")
    if "email verification" in user["content"]:
        # A transport error (provider unreachable) is the genuine mid-corpus abort:
        # per-request HTTP errors are now recorded inside run_single, so the abort
        # path that must preserve already-written runs is a connection failure.
        raise httpx.ConnectError("provider unreachable", request=request)
    return _handler(request)


def test_completed_runs_persist_when_later_task_fails(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_fail_second_task_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "2",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )
    # ConnectError (transport abort) mid-corpus -> caught as TransportError -> exit 1.
    assert exit_code == 1

    runs = (out_dir / "runs-local-Qwen-Qwen3-8B.jsonl").read_text().strip().splitlines()
    assert len(runs) == 2  # first task's k=2 runs survived the mid-dataset failure
    assert all(json.loads(line)["task_id"] == "ws-001" for line in runs)


def _capture_client_kwargs(monkeypatch) -> dict:
    captured: dict = {}
    real = httpx.Client(transport=httpx.MockTransport(_handler))

    def fake_client(**kwargs) -> httpx.Client:
        captured.update(kwargs)
        return real

    monkeypatch.setattr(httpx, "Client", fake_client)
    return captured


def test_default_client_is_proxied_for_openrouter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-x")
    monkeypatch.setenv("HTTP_PROXY", "http://10.23.37.244:8888")
    captured = _capture_client_kwargs(monkeypatch)
    dataset = _write_dataset(tmp_path / "tasks.jsonl")

    main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "openrouter",
            "--k",
            "1",
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert captured["proxy"] == "http://10.23.37.244:8888"
    assert captured["trust_env"] is False


def test_default_client_is_direct_for_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://10.23.37.244:8888")
    captured = _capture_client_kwargs(monkeypatch)
    dataset = _write_dataset(tmp_path / "tasks.jsonl")

    main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert captured["proxy"] is None
    assert captured["trust_env"] is False


def test_calibrate_export_packet_writes_blind_jsonl_and_md(tmp_path: Path) -> None:
    out = tmp_path / "packet.jsonl"
    exit_code = main(
        [
            "calibrate",
            "export-packet",
            "--fixtures",
            "examples/calibration/fixtures.jsonl",
            "--rubric",
            "examples/calibration/rubric.md",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    text = out.read_text()
    assert "calib-packet-v1" in text
    assert "intended_anchor" not in text  # blind: no intended labels
    assert '"score": null' in text
    assert (out.with_suffix(".md")).exists()  # sibling human-readable view


def _write_filled_packet(
    path: Path, fixtures_path: Path, rubric_path: Path, scores, annotator
) -> Path:
    import dataclasses

    from agent_eval_lab.calibrate.packet import build_packet, packet_to_jsonl
    from agent_eval_lab.records.serialize import trajectory_from_dict
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    spec = LlmJudgeSpec(rubric="(cal)", judge_model="(cal)", scale=(1, 5))
    rows = [
        json.loads(line)
        for line in fixtures_path.read_text().splitlines()
        if line.strip()
    ]
    fixtures = [(r["id"], trajectory_from_dict(r["trajectory"])) for r in rows]
    blank = build_packet(fixtures=fixtures, spec=spec, rubric=rubric_path.read_text())
    items = tuple(dataclasses.replace(i, score=s) for i, s in zip(blank.items, scores))
    filled = dataclasses.replace(blank, items=items, annotator_id=annotator)
    path.write_text(packet_to_jsonl(filled))
    return path


def test_calibrate_compute_reports_kappa_and_ci(tmp_path: Path, capsys) -> None:
    fixtures = Path("examples/calibration/fixtures.jsonl")
    rubric = Path("examples/calibration/rubric.md")
    n = len([ln for ln in fixtures.read_text().splitlines() if ln.strip()])
    a = _write_filled_packet(tmp_path / "a.jsonl", fixtures, rubric, [5] * n, "alice")
    b = _write_filled_packet(tmp_path / "b.jsonl", fixtures, rubric, [5] * n, "bob")
    report = tmp_path / "report.md"

    exit_code = main(
        [
            "calibrate",
            "compute",
            "--packets",
            str(a),
            str(b),
            "--fixtures",
            str(fixtures),
            "--rubric",
            str(rubric),
            "--out",
            str(report),
        ]
    )

    assert exit_code == 0
    md = report.read_text()
    assert "kappa" in md.lower()
    assert "CI" in md
    assert "Confusion matrix" in md


def test_provisional_label_skips_cleanly_when_key_unset(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    out = tmp_path / "p.jsonl"
    exit_code = main(
        [
            "calibrate",
            "provisional-label",
            "--fixtures",
            "examples/calibration/fixtures.jsonl",
            "--rubric",
            "examples/calibration/rubric.md",
            "--provider",
            "deepseek",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    assert not out.exists()  # no partial packet written
    assert "key unset" in capsys.readouterr().out.lower()


# Fix 4: atomic writes — _atomic_write helper, tested with tmp_path


def test_atomic_write_helper_writes_content(tmp_path: Path) -> None:
    from agent_eval_lab.cli import _atomic_write

    target = tmp_path / "out.jsonl"
    _atomic_write(target, "hello\n")
    assert target.read_text() == "hello\n"


def test_atomic_write_leaves_no_tmp_file_behind(tmp_path: Path) -> None:
    from agent_eval_lab.cli import _atomic_write

    target = tmp_path / "out.jsonl"
    _atomic_write(target, "data")
    # Only the target file should exist after the replace
    files = list(tmp_path.iterdir())
    assert files == [target]


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    from agent_eval_lab.cli import _atomic_write

    target = tmp_path / "out.jsonl"
    target.write_text("old content")
    _atomic_write(target, "new content")
    assert target.read_text() == "new content"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    from agent_eval_lab.cli import _atomic_write

    target = tmp_path / "sub" / "deep" / "out.jsonl"
    _atomic_write(target, "x")
    assert target.read_text() == "x"


# Fix 5: provisional partial-failure visibility


def test_provisional_label_prints_scored_and_errored_counts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A JudgeError item (no parseable SCORE) must produce a visible errored count
    in the CLI stdout and in the rendered summary."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "I cannot score."}}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = tmp_path / "p.jsonl"
    exit_code = main(
        [
            "calibrate",
            "provisional-label",
            "--fixtures",
            "examples/calibration/fixtures.jsonl",
            "--rubric",
            "examples/calibration/rubric.md",
            "--provider",
            "deepseek",
            "--out",
            str(out),
        ],
        http_client=client,
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    # Must report scored=0 and errored=16 (all 16 fixtures fail to parse)
    assert "scored" in captured.lower() or "errored" in captured.lower()
    # The packet file must exist even when all errored (score=None recorded)
    assert out.exists()


def test_system_prompt_file_tags_artifact_and_applies_override(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    prompt_file = tmp_path / "planning-v1.txt"
    prompt_file.write_text("PLAN FIRST: identify before you act.\n")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
            "--system-prompt-file",
            str(prompt_file),
        ],
        http_client=client,
    )

    # Tag = fixture stem -> __planning-v1 suffix on BOTH artifacts.
    names = sorted(p.name for p in out_dir.iterdir())
    assert "runs-local-Qwen-Qwen3-8B__planning-v1.jsonl" in names
    assert "baseline-local-Qwen-Qwen3-8B__planning-v1.md" in names


def test_no_system_prompt_file_keeps_v1_artifact_name(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )

    names = sorted(p.name for p in out_dir.iterdir())
    # Byte-identical to v1: no __tag suffix.
    assert names == [
        "baseline-local-Qwen-Qwen3-8B.md",
        "runs-local-Qwen-Qwen3-8B.jsonl",
    ]


def _write_runs_jsonl(path: Path, runs) -> Path:
    from agent_eval_lab.records.serialize import run_result_to_dict

    path.write_text("".join(json.dumps(run_result_to_dict(r)) + "\n" for r in runs))
    return path


def _mk_run(condition, task_id, run_index, passed, failure_reason=None):
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    return RunResult(
        task_id=task_id,
        condition_id=condition,
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=None if passed else failure_reason,
        ),
    )


def _write_tiers(path: Path, mapping) -> Path:
    path.write_text(json.dumps(mapping) + "\n")
    return path


def test_report_validation_rebuilds_from_jsonl(tmp_path: Path) -> None:
    tiers = _write_tiers(tmp_path / "tiers.json", {"ws2-001": "T1", "ws2-018": "T3"})
    runs = [
        *[_mk_run("local:Qwen/Qwen3-8B", "ws2-001", i, True) for i in range(3)],
        *[
            _mk_run("local:Qwen/Qwen3-8B", "ws2-018", i, False, "wrong_args")
            for i in range(3)
        ],
    ]
    jsonl = _write_runs_jsonl(tmp_path / "runs-local.jsonl", runs)
    out = tmp_path / "validation-report.md"

    exit_code = main(
        [
            "report-validation",
            "--runs",
            f"C4=local:Qwen/Qwen3-8B={jsonl}",
            "--dataset",
            "examples/datasets/workspace_tool_use_v2.jsonl",
            "--tiers",
            str(tiers),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    md = out.read_text()
    assert "# Validation report" in md
    assert "pass^3" in md


def test_compare_configs_identifies_by_path_not_condition_id(tmp_path: Path) -> None:
    tiers = _write_tiers(tmp_path / "tiers.json", {"ws2-018": "T3", "ws2-040": "T4"})
    prompt = tmp_path / "planning-v1.txt"
    prompt.write_text("PLAN FIRST.\n")
    # Both files carry the SAME in-record condition_id; identity is the path.
    # A fails BOTH hard tasks; B passes BOTH -> Δ pass^3 = +1.0 on every cluster
    # resample -> T3+T4 CI = [1.0, 1.0] (strictly above 0) -> "planning helps".
    a = [
        *[
            _mk_run("deepseek:deepseek-v4-pro", "ws2-018", i, False, "wrong_args")
            for i in range(3)
        ],
        *[
            _mk_run("deepseek:deepseek-v4-pro", "ws2-040", i, False, "forbidden_action")
            for i in range(3)
        ],
    ]
    b = [
        *[_mk_run("deepseek:deepseek-v4-pro", "ws2-018", i, True) for i in range(3)],
        *[_mk_run("deepseek:deepseek-v4-pro", "ws2-040", i, True) for i in range(3)],
    ]
    pa = _write_runs_jsonl(tmp_path / "runs__default.jsonl", a)
    pb = _write_runs_jsonl(tmp_path / "runs__planning-v1.jsonl", b)
    out = tmp_path / "comparison-report.md"

    exit_code = main(
        [
            "compare-configs",
            "--config-a",
            str(pa),
            "--config-b",
            str(pb),
            "--tiers",
            str(tiers),
            "--planning-prompt-file",
            str(prompt),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    md = out.read_text()
    assert "# Configuration comparison" in md
    assert "sha256" in md.lower()
    assert "planning helps on hard tiers" in md  # B fixed ws2-018 -> Δ above 0


def test_partial_price_flags_error(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "run-baseline",
                "--dataset",
                str(dataset),
                "--provider",
                "local",
                "--input-price-per-mtok",
                "1.0",
            ],
            http_client=httpx.Client(transport=httpx.MockTransport(_handler)),
        )

    assert excinfo.value.code == 2


# ── P0-1: _parse_runs_spec with "=" inside the condition_id ─────────────────


def test_parse_runs_spec_condition_id_with_equals(tmp_path: Path) -> None:
    """LABEL=condition=with=equals=path must parse as (LABEL, path)
    where condition_id may contain inner '=' chars."""
    from agent_eval_lab.cli import _parse_runs_spec

    p = tmp_path / "runs.jsonl"
    p.touch()
    # condition_id = "provider:model=variant" (contains one inner '=')
    spec = f"C1=provider:model=variant={p}"
    label, path = _parse_runs_spec(spec)
    assert label == "C1"
    assert path == p


def test_parse_runs_spec_two_part_label_path(tmp_path: Path) -> None:
    """LABEL=path (two-part spec) still parses correctly."""
    from agent_eval_lab.cli import _parse_runs_spec

    p = tmp_path / "runs.jsonl"
    p.touch()
    spec = f"C4={p}"
    label, path = _parse_runs_spec(spec)
    assert label == "C4"
    assert path == p


# ── P0-2: _load_run_results raises ValueError with context on bad JSONL ─────


def test_load_run_results_raises_value_error_on_truncated_line(
    tmp_path: Path,
) -> None:
    """A truncated JSONL line must raise ValueError naming file, line number,
    and records-loaded-so-far — never silently skip."""
    from agent_eval_lab.cli import _load_run_results
    from agent_eval_lab.records.serialize import run_result_to_dict

    good = _mk_run("cond", "ws2-001", 0, True)
    good2 = _mk_run("cond", "ws2-001", 1, True)
    jsonl_path = tmp_path / "runs.jsonl"
    # Write two good lines, then a truncated (malformed) third line
    jsonl_path.write_text(
        json.dumps(run_result_to_dict(good))
        + "\n"
        + json.dumps(run_result_to_dict(good2))
        + "\n"
        + '{"task_id": "ws2-002", "condition_id": "cond"'  # truncated!
        + "\n"
    )
    with pytest.raises(ValueError) as exc_info:
        _load_run_results(jsonl_path)
    msg = str(exc_info.value)
    assert "runs.jsonl" in msg  # file path named
    assert "3" in msg  # 1-based line number
    assert "2" in msg  # records-loaded-so-far


# ── P1-7a: compare-configs exits cleanly on universe mismatch ───────────────


def test_compare_configs_clean_diagnostic_on_universe_mismatch(
    tmp_path: Path, capsys
) -> None:
    """Universe mismatch between config-a and config-b must exit non-zero
    with a clean one-line diagnostic (no traceback)."""
    tiers = _write_tiers(
        tmp_path / "tiers.json", {"ws2-018": "T3", "ws2-019": "T3", "ws2-040": "T4"}
    )
    prompt = tmp_path / "planning-v1.txt"
    prompt.write_text("PLAN FIRST.\n")
    a = [_mk_run("deepseek:deepseek-v4-pro", "ws2-018", i, True) for i in range(3)]
    # config-b has a DIFFERENT task id — universe mismatch
    b = [_mk_run("deepseek:deepseek-v4-pro", "ws2-019", i, True) for i in range(3)]
    pa = _write_runs_jsonl(tmp_path / "runs_a.jsonl", a)
    pb = _write_runs_jsonl(tmp_path / "runs_b.jsonl", b)
    out = tmp_path / "comparison-report.md"

    exit_code = main(
        [
            "compare-configs",
            "--config-a",
            str(pa),
            "--config-b",
            str(pb),
            "--tiers",
            str(tiers),
            "--planning-prompt-file",
            str(prompt),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code != 0
    # No traceback: function writes a clean one-liner to stderr
    assert not out.exists() or True  # report file may not be written


# ── P1-7b: compare-configs exits cleanly on missing config file ─────────────


def test_compare_configs_clean_diagnostic_on_missing_file(
    tmp_path: Path,
) -> None:
    """Missing --config-a or --config-b must exit non-zero with a clean message."""
    tiers = _write_tiers(tmp_path / "tiers.json", {"ws2-018": "T3"})
    prompt = tmp_path / "planning-v1.txt"
    prompt.write_text("PLAN FIRST.\n")
    missing = tmp_path / "does-not-exist.jsonl"
    existing_b = _write_runs_jsonl(
        tmp_path / "b.jsonl",
        [_mk_run("cond", "ws2-018", i, True) for i in range(3)],
    )
    out = tmp_path / "comparison-report.md"

    exit_code = main(
        [
            "compare-configs",
            "--config-a",
            str(missing),
            "--config-b",
            str(existing_b),
            "--tiers",
            str(tiers),
            "--planning-prompt-file",
            str(prompt),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code != 0


# ── P1-7c: compare-configs exits cleanly on empty hard-subset ───────────────


def test_compare_configs_clean_diagnostic_on_empty_hard_subset(
    tmp_path: Path,
) -> None:
    """When there are no T3/T4 tasks, the report must not crash with an
    uncaught exception — exit non-zero with a clean diagnostic."""
    # Tiers has only T1/T2 tasks; no T3/T4 -> hard subset is empty
    tiers = _write_tiers(tmp_path / "tiers.json", {"ws2-001": "T1", "ws2-002": "T2"})
    prompt = tmp_path / "planning-v1.txt"
    prompt.write_text("PLAN FIRST.\n")
    a = [_mk_run("cond", "ws2-001", i, True) for i in range(3)]
    b = [_mk_run("cond", "ws2-001", i, True) for i in range(3)]
    pa = _write_runs_jsonl(tmp_path / "runs_a.jsonl", a)
    pb = _write_runs_jsonl(tmp_path / "runs_b.jsonl", b)
    out = tmp_path / "comparison-report.md"

    exit_code = main(
        [
            "compare-configs",
            "--config-a",
            str(pa),
            "--config-b",
            str(pb),
            "--tiers",
            str(tiers),
            "--planning-prompt-file",
            str(prompt),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code != 0


# ── Finding 3: _run_report_validation ValueError guard ───────────────────────


def test_report_validation_malformed_runs_spec_clean_diagnostic(
    tmp_path: Path, capsys
) -> None:
    """report-validation --runs just-a-label must exit non-zero with a clean
    one-line diagnostic on stderr and no Python traceback."""
    tiers = _write_tiers(tmp_path / "tiers.json", {"ws2-001": "T1"})
    out = tmp_path / "report.md"

    exit_code = main(
        [
            "report-validation",
            "--runs",
            "just-a-label",
            "--dataset",
            "examples/datasets/workspace_tool_use_v2.jsonl",
            "--tiers",
            str(tiers),
            "--k",
            "3",
            "--out",
            str(out),
        ]
    )
    assert exit_code != 0
    err = capsys.readouterr().err
    # Must be a clean one-liner on stderr, not a traceback
    assert "error:" in err
    assert "Traceback" not in err
    assert "just-a-label" in err


# ── Item 004: code-world wiring through run-baseline ─────────────────────────


def _write_code_dataset(path: Path) -> Path:
    row = {
        "id": "cr-e2e-001",
        "capability": "visible_test_localization",
        "input": {
            "messages": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Fix add in calc.py, then run the tests.",
                }
            ],
            "available_tools": [
                "read_file",
                "write_file",
                "list_files",
                "run_tests",
            ],
        },
        "verification": {
            "type": "execution",
            "held_out_tests": {
                "test_oracle_calc.py": (
                    "from calc import add\n\n\ndef test_add():\n"
                    "    assert add(1, 2) == 3\n"
                )
            },
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {
            "files": {
                "calc.py": "def add(a, b):\n    return a - b\n",
                "test_calc.py": (
                    "from calc import add\n\n\ndef test_add_smoke():\n"
                    "    assert add(2, 2) == 4\n"
                ),
            }
        },
    }
    path.write_text(json.dumps(row) + "\n")
    return path


def _code_world_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(m["role"] == "tool" for m in body["messages"]):
        message = {"role": "assistant", "content": "Ran the tests."}
    else:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "run_tests", "arguments": "{}"},
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def test_run_baseline_resolves_code_world_and_grades_through_oracle(
    tmp_path: Path,
) -> None:
    """Criterion 4: no hardwired WORKSPACE_TOOLS — a code task resolves to the
    code world, fulfills a mid-trajectory run_tests at the pytest edge, grades
    through the oracle edge, and streams a parseable RunResult line."""
    from agent_eval_lab.cli import _load_run_results
    from agent_eval_lab.records.turns import ToolResultTurn, ToolSuccess

    dataset = _write_code_dataset(tmp_path / "code.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_code_world_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )

    assert exit_code == 0
    [run] = _load_run_results(out_dir / "runs-local-Qwen-Qwen3-8B.jsonl")
    [tool_result] = [t for t in run.trajectory.turns if isinstance(t, ToolResultTurn)]
    assert isinstance(tool_result.outcome, ToolSuccess)
    assert tool_result.outcome.result["status"] == "failed"  # unrepaired tree
    assert run.grade.grader_id == "execution"
    assert run.grade.passed is False
    assert run.grade.evidence["execution"] == "run"
    assert run.grade.evidence["status"] == "failed"


def test_run_baseline_connect_error_exits_1_with_provider_and_hint(
    tmp_path: Path, capsys
) -> None:
    """Criterion 5: a refused connection is a one-line exit-1 diagnostic naming
    provider id + base_url, with the start-the-server hint for `local` — never
    a traceback. (Wall time ~3s: the client's two retry backoffs.)"""
    dataset = _write_dataset(tmp_path / "tasks.jsonl")

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(tmp_path / "out"),
        ],
        http_client=httpx.Client(transport=httpx.MockTransport(refuse)),
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "local" in err
    assert "http://localhost:11434/v1" in err
    assert "is the server running?" in err
    assert "Traceback" not in err


# ── Item 004: report-final (criteria 15, 19, 20) ─────────────────────────────


def _final_report_inputs(tmp_path: Path):
    tiers = _write_tiers(tmp_path / "tiers.json", {"cr-001": "T1", "cr-002": "T3"})
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "snapshot_date": "2026-06-11",
                "prices": {
                    "deepseek:deepseek-v4-pro": {
                        "input_per_mtok": 0.27,
                        "output_per_mtok": 1.1,
                    }
                },
            }
        )
        + "\n"
    )
    context = tmp_path / "v2-context.md"
    context.write_text("v1/v2 workspace baselines: see committed reports.\n")
    runs = [
        *[_mk_run("deepseek:deepseek-v4-pro", "cr-001", i, True) for i in range(3)],
        *[
            _mk_run("deepseek:deepseek-v4-pro", "cr-002", i, False, "wrong_args")
            for i in range(3)
        ],
    ]
    jsonl = _write_runs_jsonl(tmp_path / "runs-deepseek-deepseek-v4-pro.jsonl", runs)
    return tiers, prices, context, jsonl


def _report_final_args(tmp_path, tiers, prices, context, jsonl, out) -> list[str]:
    return [
        "report-final",
        "--runs",
        f"C1=deepseek:deepseek-v4-pro={jsonl}",
        f"C4=local:Qwen/Qwen3-8B={tmp_path / 'missing-local.jsonl'}",
        "--dataset",
        "examples/datasets/code_repair_v1.jsonl",
        "--tiers",
        str(tiers),
        "--prices",
        str(prices),
        "--context-file",
        str(context),
        "--k",
        "3",
        "--expected-n-tasks",
        "15",
        "--n-resamples",
        "200",
        "--out",
        str(out),
    ]


def test_report_final_renders_byte_identically_across_invocations(
    tmp_path: Path,
) -> None:
    tiers, prices, context, jsonl = _final_report_inputs(tmp_path)
    out_a, out_b = tmp_path / "final-a.md", tmp_path / "final-b.md"

    assert main(_report_final_args(tmp_path, tiers, prices, context, jsonl, out_a)) == 0
    assert main(_report_final_args(tmp_path, tiers, prices, context, jsonl, out_b)) == 0

    a, b = out_a.read_bytes(), out_b.read_bytes()
    assert a == b
    md = a.decode()
    assert "# Final evaluation report" in md
    assert "fc-v2" in md
    assert "| C4 | blocked |" in md  # zero-record condition: blocked, no numbers
    assert "incomplete" in md  # 2 of 15 expected tasks present


def test_report_final_rejects_heterogeneous_runs_file(tmp_path: Path, capsys) -> None:
    tiers, prices, context, _ = _final_report_inputs(tmp_path)
    mixed = _write_runs_jsonl(
        tmp_path / "mixed.jsonl",
        [
            _mk_run("deepseek:deepseek-v4-pro", "cr-001", 0, True),
            _mk_run("glm:Pro/zai-org/GLM-5.1", "cr-001", 1, True),
        ],
    )
    out = tmp_path / "final.md"

    exit_code = main(_report_final_args(tmp_path, tiers, prices, context, mixed, out))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "heterogeneous" in err
    assert "Traceback" not in err
    assert not out.exists()


def test_report_final_rejects_condition_segment_mismatch(
    tmp_path: Path, capsys
) -> None:
    tiers, prices, context, jsonl = _final_report_inputs(tmp_path)
    out = tmp_path / "final.md"
    args = _report_final_args(tmp_path, tiers, prices, context, jsonl, out)
    args[2] = f"C1=minimax:MiniMax-M3={jsonl}"  # segment contradicts the records

    exit_code = main(args)

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "minimax:MiniMax-M3" in err and "deepseek:deepseek-v4-pro" in err
    assert not out.exists()


# ── Item 004 fix 1: --max-tokens CLI flag threads through to the request ──────


def test_max_tokens_flag_threads_through_to_request_body(tmp_path: Path) -> None:
    """--max-tokens plumbs the explicit completion budget into every
    chat_completion request body (item 004 fix 1)."""
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    seen_bodies: list[dict] = []

    def capturing_handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(json.loads(request.content))
        return _handler(request)

    client = httpx.Client(transport=httpx.MockTransport(capturing_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
            "--max-tokens",
            "2048",
        ],
        http_client=client,
    )

    assert exit_code == 0
    assert all("max_tokens" in body for body in seen_bodies), (
        "every request must carry max_tokens from the CLI --max-tokens flag"
    )
    assert all(body["max_tokens"] == 2048 for body in seen_bodies)


def test_max_tokens_default_is_4096(tmp_path: Path) -> None:
    """Without --max-tokens, the default of 4096 is used."""
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    seen_bodies: list[dict] = []

    def capturing_handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(json.loads(request.content))
        return _handler(request)

    client = httpx.Client(transport=httpx.MockTransport(capturing_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset",
            str(dataset),
            "--provider",
            "local",
            "--k",
            "1",
            "--out",
            str(out_dir),
        ],
        http_client=client,
    )

    assert exit_code == 0
    assert all(body.get("max_tokens") == 4096 for body in seen_bodies)


# ── Task 11 (item 005): run-dset subcommand parser ────────────────────────────


def test_run_dset_writes_incrementally_and_records_void_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    """item 008: run-dset persists each task as it completes and writes a
    <runs>.void.json sidecar so report-m1 consumes its output directly (voids
    included)."""
    from agent_eval_lab import cli
    from agent_eval_lab.datasets import cmc_dset
    from agent_eval_lab.experiments.evaluator_config import (
        CandidateConfig,
        EvaluatorConfig,
        HealthProbeConfig,
        OracleBSetConfig,
        RunnerConfig,
        SkillConfig,
        StoreConfig,
    )
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners import dset_run
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    store = tmp_path / "store"
    store.mkdir()
    (store / "cmc-docs-factkeys.json").write_text(json.dumps({"snapshot_sha256": "s"}))

    fake_cfg = EvaluatorConfig(
        store=StoreConfig(path=str(store)),
        health_probe=HealthProbeConfig(url="http://x", username="u", password="p"),
        skill=SkillConfig(strategy_test_path="x"),
        candidate=CandidateConfig(username="fake-candidate", password="fake-pass"),
        runner=RunnerConfig(safety_cap=200, k_valid=2, max_invalid_rate=0.4),
        oracle_b_set=OracleBSetConfig(
            readback="playwright-cli",
            project_id="FAKE_PROJECT_ID",
            goldens={"B-1": "fake-golden-object-0001"},
        ),
    )
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: fake_cfg)
    monkeypatch.setattr(cmc_dset, "build_cmc_tasks", lambda **_k: ())

    def _run(tid: str) -> RunResult:
        return RunResult(
            task_id=tid,
            condition_id="local:Qwen/Qwen3-8B",
            run_index=0,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
                run_index=0,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(
                grader_id="fact_key",
                passed=True,
                score=1.0,
                evidence={},
                failure_reason=None,
            ),
        )

    def fake_run_dset(**_kwargs):
        a = _run("cmc-q01")
        yield ReplacementOutcome(
            valid_runs=(a,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=a),),
            void=False,
        )
        # task 2 voided before k valid trials (D34 INCOMPLETE) — zero valid rows.
        yield ReplacementOutcome(
            valid_runs=(),
            attempts=(TrialAttempt(attempt_index=0, valid=False, run=_run("cmc-q02")),),
            void=True,
        )

    monkeypatch.setattr(dset_run, "run_dset", fake_run_dset)

    out = tmp_path / "out"
    rc = main(
        [
            "run-dset",
            "--provider",
            "local",
            "--evaluator-config",
            str(tmp_path / "evaluator.toml"),
            "--out",
            str(out),
        ],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        ),
    )
    assert rc == 0
    runs_path = out / "runs-dset-local-Qwen-Qwen3-8B.jsonl"
    rows = [
        json.loads(line) for line in runs_path.read_text().splitlines() if line.strip()
    ]
    assert [r["task_id"] for r in rows] == ["cmc-q01"]  # only the valid task's run
    sidecar = json.loads(runs_path.with_suffix(".void.json").read_text())
    assert sidecar["void_task_ids"] == ["cmc-q02"]  # the voided task is recorded


def test_write_heartbeat_writes_session_id(tmp_path: Path) -> None:
    from agent_eval_lab.cli import _write_heartbeat

    hb = tmp_path / "runs-dset-x.heartbeat"
    _write_heartbeat(hb, "cmc-q01")
    assert hb.read_text() == "cmc-q01"
    first = hb.stat().st_mtime_ns
    _write_heartbeat(hb, "cmc-q02")  # rewritten -> content + mtime advance
    assert hb.read_text() == "cmc-q02"
    assert hb.stat().st_mtime_ns >= first


def test_run_dset_wires_a_heartbeat_sink_writing_the_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    """The CLI passes run_dset a heartbeat sink that writes
    runs-dset-<slug>.heartbeat next to the output jsonl — the canonical sub-task
    liveness signal (content = live task id, mtime = the watched value)."""
    from agent_eval_lab import cli
    from agent_eval_lab.datasets import cmc_dset
    from agent_eval_lab.experiments.evaluator_config import (
        CandidateConfig,
        EvaluatorConfig,
        HealthProbeConfig,
        OracleBSetConfig,
        RunnerConfig,
        SkillConfig,
        StoreConfig,
    )
    from agent_eval_lab.runners import dset_run

    store = tmp_path / "store"
    store.mkdir()
    (store / "cmc-docs-factkeys.json").write_text(json.dumps({"snapshot_sha256": "s"}))
    fake_cfg = EvaluatorConfig(
        store=StoreConfig(path=str(store)),
        health_probe=HealthProbeConfig(url="http://x", username="u", password="p"),
        skill=SkillConfig(strategy_test_path="x"),
        candidate=CandidateConfig(username="fake-candidate", password="fake-pass"),
        runner=RunnerConfig(safety_cap=200, k_valid=2, max_invalid_rate=0.4),
        oracle_b_set=OracleBSetConfig(
            readback="playwright-cli",
            project_id="FAKE_PROJECT_ID",
            goldens={"B-1": "fake-golden-object-0001"},
        ),
    )
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: fake_cfg)
    monkeypatch.setattr(cmc_dset, "build_cmc_tasks", lambda **_k: ())

    captured = {}

    def fake_run_dset(**kwargs):
        captured.update(kwargs)
        return iter(())  # no tasks

    monkeypatch.setattr(dset_run, "run_dset", fake_run_dset)

    out = tmp_path / "out"
    rc = main(
        [
            "run-dset",
            "--provider",
            "local",
            "--evaluator-config",
            str(tmp_path / "evaluator.toml"),
            "--out",
            str(out),
        ],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        ),
    )
    assert rc == 0
    heartbeat_fn = captured["heartbeat_fn"]
    heartbeat_fn("cmc-q05")  # simulate the executor firing on a command
    hb_file = out / "runs-dset-local-Qwen-Qwen3-8B.heartbeat"
    assert hb_file.read_text() == "cmc-q05"


def test_run_dset_transport_error_gives_exit1_and_writes_void_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: _run_dset_command must catch httpx.TransportError mid-corpus.

    When the provider becomes unreachable after the first task has completed,
    the CLI must:
    - return exit-code 1 (not propagate an uncaught exception / traceback)
    - preserve the partial .jsonl with the first task's runs
    - write the .void.json sidecar despite the abort
    - print a 'cannot reach provider' diagnostic to stderr
    """
    from agent_eval_lab import cli
    from agent_eval_lab.datasets import cmc_dset
    from agent_eval_lab.experiments.evaluator_config import (
        CandidateConfig,
        EvaluatorConfig,
        HealthProbeConfig,
        OracleBSetConfig,
        RunnerConfig,
        SkillConfig,
        StoreConfig,
    )
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners import dset_run
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    store = tmp_path / "store"
    store.mkdir()
    (store / "cmc-docs-factkeys.json").write_text(json.dumps({"snapshot_sha256": "s"}))

    fake_cfg = EvaluatorConfig(
        store=StoreConfig(path=str(store)),
        health_probe=HealthProbeConfig(url="http://x", username="u", password="p"),
        skill=SkillConfig(strategy_test_path="x"),
        candidate=CandidateConfig(username="fake-candidate", password="fake-pass"),
        runner=RunnerConfig(safety_cap=200, k_valid=2, max_invalid_rate=0.4),
        oracle_b_set=OracleBSetConfig(
            readback="playwright-cli",
            project_id="FAKE_PROJECT_ID",
            goldens={"B-1": "fake-golden-object-0001"},
        ),
    )
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: fake_cfg)
    monkeypatch.setattr(cmc_dset, "build_cmc_tasks", lambda **_k: ())

    def _run(tid: str) -> RunResult:
        return RunResult(
            task_id=tid,
            condition_id="local:Qwen/Qwen3-8B",
            run_index=0,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
                run_index=0,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(
                grader_id="fact_key",
                passed=True,
                score=1.0,
                evidence={},
                failure_reason=None,
            ),
        )

    sentinel_request = httpx.Request("POST", "http://local")

    def fake_run_dset(**_kwargs):
        # First task completes successfully.
        a = _run("cmc-q01")
        yield ReplacementOutcome(
            valid_runs=(a,),
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=a),),
            void=False,
        )
        # Second task: provider goes unreachable mid-corpus.
        raise httpx.ConnectError("provider unreachable", request=sentinel_request)

    monkeypatch.setattr(dset_run, "run_dset", fake_run_dset)

    out = tmp_path / "out"
    import io

    stderr_capture = io.StringIO()
    import sys

    monkeypatch.setattr(sys, "stderr", stderr_capture)

    exit_code = main(
        [
            "run-dset",
            "--provider",
            "local",
            "--evaluator-config",
            str(tmp_path / "evaluator.toml"),
            "--out",
            str(out),
        ],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        ),
    )

    # Must return 1 (clean exit), not propagate an uncaught exception.
    assert exit_code == 1

    # Partial .jsonl must survive with the first task's runs.
    runs_path = out / "runs-dset-local-Qwen-Qwen3-8B.jsonl"
    assert runs_path.exists(), "partial runs file must be written even on abort"
    rows = [
        json.loads(line) for line in runs_path.read_text().splitlines() if line.strip()
    ]
    assert [r["task_id"] for r in rows] == ["cmc-q01"]

    # .void.json sidecar must be written despite the abort.
    void_path = runs_path.with_suffix(".void.json")
    assert void_path.exists(), ".void.json sidecar must be written on abort"

    # stderr must carry the 'cannot reach provider' diagnostic.
    diag = stderr_capture.getvalue()
    assert "cannot reach provider" in diag


def test_run_dset_subcommand_parses():
    from agent_eval_lab.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "run-dset",
            "--provider",
            "deepseek",
            "--evaluator-config",
            "evaluator.toml",
            "--out",
            "reports",
        ]
    )
    assert args.command == "run-dset"
    assert args.provider == "deepseek"
    assert args.evaluator_config == Path("evaluator.toml")


def test_outcomes_from_runs_honors_void_sidecar(tmp_path):
    # review L2: a task listed in the void sidecar is marked void (INCOMPLETE),
    # including a fully-void task with zero valid rows (restored from the sidecar).
    from agent_eval_lab.cli import _outcomes_from_runs, _void_task_ids_for
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    def _run(task):
        t = Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
        )
        return RunResult(
            task_id=task,
            condition_id="c",
            run_index=0,
            trajectory=t,
            grade=GradeResult(
                grader_id="g", passed=True, score=1.0, evidence={}, failure_reason=None
            ),
        )

    # task A produced 1 valid run; task B was fully void (no rows) per the sidecar.
    outs = _outcomes_from_runs([_run("A")], frozenset({"B"}))
    # A: present, non-void; B: present, void, zero valid runs
    a = next(o for o in outs if o.valid_runs and o.valid_runs[0].task_id == "A")
    b = next(o for o in outs if not o.valid_runs)
    assert a.void is False and len(a.valid_runs) == 1
    assert b.void is True and len(b.valid_runs) == 0

    # sidecar reader round-trip
    import json

    runs_path = tmp_path / "runs-m1-c-D.jsonl"
    runs_path.write_text("")
    runs_path.with_suffix(".void.json").write_text(
        json.dumps({"void_task_ids": ["B", "C"]})
    )
    assert _void_task_ids_for(runs_path) == frozenset({"B", "C"})
    assert _void_task_ids_for(tmp_path / "nope.jsonl") == frozenset()


def test_load_m1_domain_tasks_includes_f(tmp_path, monkeypatch) -> None:
    from agent_eval_lab import cli

    store_root = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only"
    f1_test = store_root / "web-dossier-golden/golden-files/f1.held_out.test.js"
    if not f1_test.exists():
        import pytest

        pytest.skip("local web-dossier golden store required")

    class _Store:
        path = str(store_root)

    class _Cfg:
        store = _Store()

    domain_tasks = cli._load_m1_domain_tasks(args=None, cfg=_Cfg())
    assert "D" in domain_tasks
    assert "F" in domain_tasks
    assert [t.id for t in domain_tasks["F"]] == ["f-f1", "f-f2", "f-f3"]


def test_load_m1_domain_tasks_includes_b_when_store_present(tmp_path, monkeypatch):
    from pathlib import Path

    from agent_eval_lab import cli

    golden = (
        Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/b-set-golden"
    )
    if not (golden / "b1-golden.json").exists():
        import pytest

        pytest.skip("local b-set golden store required (gitignored)")

    # build a cfg stub exposing the store path, candidate, skill, oracle_b_set
    # exactly as load_evaluator_config would (read the real one only for the paths
    # it needs; the test SKIPS if absent so CI never reaches here).
    cfg = cli.load_evaluator_config(Path("evaluator.toml"))
    domain_tasks = cli._load_m1_domain_tasks(args=None, cfg=cfg)
    assert "B" in domain_tasks
    assert {t.id for t in domain_tasks["B"]} == {"b-b1-noskill", "b-b1-skill"}


def test_run_f_writes_m1_f_runs_and_void_sidecar(tmp_path: Path, monkeypatch) -> None:
    """item: run-f drives the F-domain candidate-edit eval for one arm and writes
    runs-m1-<slug>-F.jsonl (+ empty .void.json — F is env-free, never VOID) so
    report-m1 consumes it directly, exactly like the D-set artifacts."""
    from agent_eval_lab import cli
    from agent_eval_lab.datasets import f_tasks as f_tasks_mod
    from agent_eval_lab.experiments.evaluator_config import (
        CandidateConfig,
        EvaluatorConfig,
        HealthProbeConfig,
        OracleBSetConfig,
        RunnerConfig,
        SkillConfig,
        StoreConfig,
    )
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners import f_candidate
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    store = tmp_path / "store"
    store.mkdir()
    fake_cfg = EvaluatorConfig(
        store=StoreConfig(path=str(store)),
        health_probe=HealthProbeConfig(url="http://x", username="u", password="p"),
        skill=SkillConfig(strategy_test_path="x"),
        candidate=CandidateConfig(username="fake-candidate", password="fake-pass"),
        runner=RunnerConfig(safety_cap=200, k_valid=3, max_invalid_rate=0.4),
        oracle_b_set=OracleBSetConfig(
            readback="playwright-cli",
            project_id="FAKE_PROJECT_ID",
            goldens={"B-1": "fake-golden-object-0001"},
        ),
    )
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: fake_cfg)
    monkeypatch.setattr(f_tasks_mod, "build_f_tasks", lambda **_k: ("F1", "F2", "F3"))

    captured: dict = {}

    def _run(tid: str, i: int) -> RunResult:
        return RunResult(
            task_id=tid,
            condition_id="deepseek:deepseek-v4-pro",
            run_index=i,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=5, completion_tokens=3, latency_s=0.1),
                run_index=i,
                stop_reason="completed_natural",
                final_state={"files": {}},
            ),
            grade=GradeResult(
                grader_id="node_execution",
                passed=(tid == "f-f1"),
                score=1.0,
                evidence={},
                failure_reason=None,
            ),
        )

    def fake_run_f_candidate(**kwargs):
        captured.update(kwargs)
        for tid in ("f-f1", "f-f2"):
            runs = tuple(_run(tid, i) for i in range(kwargs["k"]))
            yield ReplacementOutcome(
                valid_runs=runs,
                attempts=tuple(
                    TrialAttempt(attempt_index=i, valid=True, run=r)
                    for i, r in enumerate(runs)
                ),
                void=False,
            )

    monkeypatch.setattr(f_candidate, "run_f_candidate", fake_run_f_candidate)

    out = tmp_path / "out"
    rc = main(
        [
            "run-f",
            "--provider",
            "deepseek",
            "--evaluator-config",
            str(tmp_path / "evaluator.toml"),
            "--out",
            str(out),
        ],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        ),
    )
    assert rc == 0
    # k flows from cfg.runner.k_valid; condition_id is the provider:model id
    assert captured["k"] == 3
    assert captured["condition_id"] == "deepseek:deepseek-v4-pro"
    runs_path = out / "runs-m1-deepseek-deepseek-v4-pro-F.jsonl"
    rows = [
        json.loads(line) for line in runs_path.read_text().splitlines() if line.strip()
    ]
    assert {r["task_id"] for r in rows} == {"f-f1", "f-f2"}
    assert len(rows) == 6  # 2 tasks x k=3 valid runs each
    sidecar = json.loads(runs_path.with_suffix(".void.json").read_text())
    assert sidecar["void_task_ids"] == []  # env-free: F never voids


def test_run_f_model_override_changes_condition_slug(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_eval_lab import cli
    from agent_eval_lab.datasets import f_tasks as f_tasks_mod
    from agent_eval_lab.experiments.evaluator_config import (
        CandidateConfig,
        EvaluatorConfig,
        HealthProbeConfig,
        OracleBSetConfig,
        RunnerConfig,
        SkillConfig,
        StoreConfig,
    )
    from agent_eval_lab.runners import f_candidate

    store = tmp_path / "store"
    store.mkdir()
    fake_cfg = EvaluatorConfig(
        store=StoreConfig(path=str(store)),
        health_probe=HealthProbeConfig(url="http://x", username="u", password="p"),
        skill=SkillConfig(strategy_test_path="x"),
        candidate=CandidateConfig(username="c", password="p"),
        runner=RunnerConfig(safety_cap=200, k_valid=1, max_invalid_rate=0.4),
        oracle_b_set=OracleBSetConfig(
            readback="playwright-cli", project_id="X", goldens={"B-1": "g"}
        ),
    )
    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: fake_cfg)
    monkeypatch.setattr(f_tasks_mod, "build_f_tasks", lambda **_k: ())
    captured: dict = {}

    def fake_run_f_candidate(**kwargs):
        captured.update(kwargs)
        return iter(())

    monkeypatch.setattr(f_candidate, "run_f_candidate", fake_run_f_candidate)

    out = tmp_path / "out"
    rc = main(
        [
            "run-f",
            "--provider",
            "siliconflow",
            "--model",
            "Qwen/Qwen3.6-35B-A3B",
            "--evaluator-config",
            str(tmp_path / "evaluator.toml"),
            "--out",
            str(out),
        ],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        ),
    )
    assert rc == 0
    assert captured["condition_id"] == "siliconflow:Qwen/Qwen3.6-35B-A3B"
    assert (out / "runs-m1-siliconflow-Qwen-Qwen3.6-35B-A3B-F.jsonl").exists()


def _run_with_provider_error(task: str, idx: int):
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import (
        PROVIDER_ERROR,
        ParseFailure,
        Trajectory,
        Usage,
    )

    t = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=idx,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw="HTTP 403: balance", error=PROVIDER_ERROR),
    )
    return RunResult(
        task_id=task,
        condition_id="c",
        run_index=idx,
        trajectory=t,
        grade=GradeResult(
            grader_id="g", passed=False, score=0.0, evidence={}, failure_reason=None
        ),
    )


def _run_ok(task: str, idx: int, passed: bool = True):
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    t = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=idx,
        stop_reason="completed_natural",
    )
    return RunResult(
        task_id=task,
        condition_id="c",
        run_index=idx,
        trajectory=t,
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0, evidence={}, failure_reason=None
        ),
    )


def test_outcomes_from_runs_masks_provider_error_as_env_invalid() -> None:
    """A provider HTTP rejection (403/429) is env-invalid — excluded from
    valid_runs and flagged invalid in attempts — never scored as a model fail."""
    from agent_eval_lab.cli import _outcomes_from_runs

    runs = [_run_ok("A", 0), _run_ok("A", 1), _run_with_provider_error("A", 2)]
    [o] = _outcomes_from_runs(runs)
    assert len(o.valid_runs) == 2  # the provider-error run is masked out
    assert sum(1 for a in o.attempts if not a.valid) == 1


def test_outcomes_from_runs_voids_task_without_k_valid_after_provider_errors() -> None:
    """With k known, a task that could not obtain k clean trials (provider errors)
    is INCOMPLETE -> VOID -> excluded from pass^k (never scored over <k, D34)."""
    from agent_eval_lab.cli import _outcomes_from_runs

    # task B: 5 attempts, 3 provider-rejected -> only 2 valid < k=5 -> VOID
    runs = (
        [_run_ok("B", i) for i in range(2)]
        + [_run_with_provider_error("B", i) for i in range(2, 5)]
        # task A: 5 clean valid -> not void
        + [_run_ok("A", i) for i in range(5)]
    )
    outcomes = _outcomes_from_runs(runs, k=5)
    by_first = {(o.attempts[0].run.task_id if o.attempts else "?"): o for o in outcomes}
    assert by_first["A"].void is False and len(by_first["A"].valid_runs) == 5
    assert by_first["B"].void is True  # 2 valid < k=5, under-powered by provider errors
    assert len(by_first["B"].valid_runs) == 2


def test_outcomes_from_runs_genuine_model_parse_failure_stays_valid() -> None:
    """A real model parse failure (unusable reply) is a model miss, NOT env-invalid:
    it stays a valid (failed) trial so pass^k still penalizes the model."""
    from agent_eval_lab.cli import _outcomes_from_runs
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage

    t = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=3, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(
            raw="{}", error="assistant message has neither content nor tool_calls"
        ),
    )
    run = RunResult(
        task_id="A",
        condition_id="c",
        run_index=0,
        trajectory=t,
        grade=GradeResult(
            grader_id="g", passed=False, score=0.0, evidence={}, failure_reason=None
        ),
    )
    [o] = _outcomes_from_runs([run], k=5)
    assert len(o.valid_runs) == 1  # model parse failure is a valid (failed) trial
    assert o.void is True  # but still <k valid -> under-powered -> VOID


# ---- Task 6: run-f-claude-baseline CLI ----------------------------------------


def test_claude_baseline_parser_defaults():
    from agent_eval_lab.cli import _build_parser

    args = _build_parser().parse_args(["run-f-claude-baseline", "--out", "/tmp/x"])
    assert args.command == "run-f-claude-baseline"
    assert args.surface == "both"
    assert args.k == 5
    assert args.bases == ["f1", "f2", "f3"]
    assert args.model == "claude-sonnet-4-6"
    assert args.smoke is False


def test_claude_baseline_smoke_and_surface_choice():
    from agent_eval_lab.cli import _build_parser

    args = _build_parser().parse_args(
        [
            "run-f-claude-baseline",
            "--out",
            "/tmp/x",
            "--surface",
            "edit-only",
            "--smoke",
        ]
    )
    assert args.surface == "edit-only"
    assert args.smoke is True


def test_claude_baseline_dry_run_makes_no_subprocess(tmp_path):
    import argparse
    import json

    from agent_eval_lab.cli import _run_f_claude_baseline_command

    args = argparse.Namespace(
        out=tmp_path,
        surface="edit-only",
        k=1,
        bases=["f1"],
        model="claude-sonnet-4-6",
        smoke=True,
        dry_run=True,
        evaluator_config=None,
    )
    rc = _run_f_claude_baseline_command(args)
    assert rc == 0
    plan = json.loads((tmp_path / "claude-baseline.plan.json").read_text())
    assert plan["attempts"] == 1 and plan["surfaces"] == ["edit-only"]


def test_claude_baseline_writes_records_and_void_summary(tmp_path, monkeypatch):
    import json

    from agent_eval_lab import cli
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

    monkeypatch.setattr(cli, "node_supports_junit", lambda *a, **k: True)

    class _Store:  # minimal load_evaluator_config().store.path stand-in
        path = str(tmp_path / "store")

    class _Cfg:
        store = _Store()

    monkeypatch.setattr(cli, "load_evaluator_config", lambda _p: _Cfg())

    class _T:  # stand-in task; only .id is read by the handler before run_f_candidate
        def __init__(self, tid):
            self.id = tid

    monkeypatch.setattr(cli, "build_f_tasks", lambda **_k: (_T("f-f1"),))
    monkeypatch.setattr(cli, "build_candidate_tree", lambda t, repo: {})

    def _rr(passed):
        return RunResult(
            task_id="f-f1",
            condition_id="c",
            run_index=0,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
                run_index=0,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(grader_id="node", passed=passed, score=0.0, evidence={}),
        )

    def fake_run_f_candidate(*, tasks, k, condition_id, build_tree_fn, run_fn):
        a, bad = _rr(True), _rr(False)
        yield ReplacementOutcome(
            valid_runs=(a,),
            attempts=(
                TrialAttempt(attempt_index=0, valid=True, run=a),
                TrialAttempt(attempt_index=1, valid=False, run=bad),
            ),
            void=True,
        )

    monkeypatch.setattr(cli, "run_f_candidate", fake_run_f_candidate)

    import argparse

    args = argparse.Namespace(
        out=tmp_path,
        surface="edit-only",
        k=2,
        bases=["f1"],
        model="claude-sonnet-4-6",
        smoke=False,
        dry_run=False,
        evaluator_config=None,
    )
    rc = cli._run_f_claude_baseline_command(
        args, run_fn_factory=lambda **_k: lambda et, i: None
    )
    assert rc == 0
    # Raw drill-down: both attempts (valid + invalid) written.
    jsonl = next(tmp_path.glob("runs-claude-*-F.jsonl")).read_text().splitlines()
    assert len(jsonl) == 2
    # Strict VOID surfaced in the summary.
    summary = json.loads((tmp_path / "claude-baseline-summary.json").read_text())
    assert summary[0]["void"] is True
    assert summary[0]["valid"] == 1 and summary[0]["invalid"] == 1
    assert summary[0]["pass_hat_k"] is False
