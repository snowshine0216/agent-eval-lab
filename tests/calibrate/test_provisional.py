import httpx

from agent_eval_lab.calibrate.provisional import run_provisional_labeling
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig

CONFIG = ProviderConfig(
    id="deepseek",
    base_url="https://api.test.example",
    api_key_env="TEST_API_KEY",
    model_id="deepseek-v4-pro",
)
RUBRIC = "Judge fidelity."


def _fixtures():
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="Done."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )
    return [("cf-01", traj), ("cf-02", traj)]


def _client(text):
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provisional_fills_packet_from_judge_calls(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk")
    packet = run_provisional_labeling(
        fixtures=_fixtures(),
        rubric=RUBRIC,
        config=CONFIG,
        annotator_id="deepseek",
        http_client=_client("Faithful.\nSCORE: 5"),
    )
    assert packet.annotator_id == "deepseek"
    assert [i.score for i in packet.items] == [5, 5]


def test_provisional_records_none_score_on_judge_error(monkeypatch) -> None:
    # A refusal -> JudgeError(parse) -> score recorded as None (annotator-failure).
    monkeypatch.setenv("TEST_API_KEY", "sk")
    packet = run_provisional_labeling(
        fixtures=_fixtures(),
        rubric=RUBRIC,
        config=CONFIG,
        annotator_id="deepseek",
        http_client=_client("I will not score."),
    )
    assert [i.score for i in packet.items] == [None, None]
