import httpx
import pytest

from agent_eval_lab.graders.judge import JudgeVerdict, build_judge_prompt, prompt_hash
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.judge_edge import JudgeError, run_judge
from agent_eval_lab.tasks.schema import LlmJudgeSpec

CONFIG = ProviderConfig(
    id="deepseek",
    base_url="https://api.test.example",
    api_key_env="TEST_API_KEY",
    model_id="deepseek-v4-pro",
)
SPEC = LlmJudgeSpec(
    rubric="Judge fidelity.", judge_model="deepseek:deepseek-v4-pro", scale=(1, 5)
)
TRAJ = Trajectory(
    turns=(MessageTurn(role="assistant", content="Done."),),
    usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
    run_index=0,
    stop_reason="completed",
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _reply(text: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_run_judge_success_stamps_model_and_hash(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    verdict = run_judge(
        spec=SPEC,
        trajectory=TRAJ,
        config=CONFIG,
        http_client=_client(
            lambda r: httpx.Response(200, json=_reply("Faithful.\nSCORE: 5"))
        ),
    )
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.score == 5
    assert verdict.judge_model == "deepseek:deepseek-v4-pro"
    assert verdict.prompt_hash == prompt_hash(
        build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    )


def test_run_judge_parse_failure_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC,
        trajectory=TRAJ,
        config=CONFIG,
        http_client=_client(
            lambda r: httpx.Response(200, json=_reply("I refuse to score."))
        ),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "parse"
    assert err.judge_model == "deepseek:deepseek-v4-pro"
    assert err.prompt_hash == prompt_hash(
        build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    )


def test_run_judge_transport_error_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    err = run_judge(
        spec=SPEC,
        trajectory=TRAJ,
        config=CONFIG,
        http_client=_client(boom),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "transport"


def test_run_judge_http_error_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC,
        trajectory=TRAJ,
        config=CONFIG,
        http_client=_client(lambda r: httpx.Response(400, json={"error": "bad"})),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "http"


def test_run_judge_empty_choices_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC,
        trajectory=TRAJ,
        config=CONFIG,
        http_client=_client(lambda r: httpx.Response(200, json={"choices": []})),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "empty_response"
