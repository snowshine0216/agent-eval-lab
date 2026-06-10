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
    report = (out_dir / "baseline-local-qwen3-8b.md").read_text()
    assert "pass@1 (trial accuracy): 1.000" in report
    assert "pass^2 (task reliability): 1.000" in report
    runs = (out_dir / "runs-local-qwen3-8b.jsonl").read_text().strip().splitlines()
    assert len(runs) == 4  # 2 tasks x k=2
    first = json.loads(runs[0])
    assert first["task_id"] == "ws-001"
    assert first["grade"]["passed"] is True
    assert str(out_dir / "baseline-local-qwen3-8b.md") in capsys.readouterr().out


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
        return httpx.Response(400, json={"error": "bad request"})
    return _handler(request)


def test_completed_runs_persist_when_later_task_fails(tmp_path: Path) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_fail_second_task_handler))

    with pytest.raises(httpx.HTTPStatusError):
        main(
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

    runs = (out_dir / "runs-local-qwen3-8b.jsonl").read_text().strip().splitlines()
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
