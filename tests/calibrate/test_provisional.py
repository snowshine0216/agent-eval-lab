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


# Fix 5: render_provisional_summary includes scored/errored counts


def _fake_report():
    """Minimal agreement report dict sufficient for render_provisional_summary."""
    return {
        "binary_kappa": {
            "point": 0.75,
            "observed_agreement": 0.875,
            "expected_agreement": 0.5,
            "degenerate": False,
            "ci": {
                "lo": 0.5,
                "hi": 1.0,
                "alpha": 0.05,
                "n_resamples": 200,
                "n_degenerate": 0,
                "seed": 42,
            },
        },
        "weighted_kappa": 0.80,
    }


def test_render_provisional_summary_includes_scored_errored_counts() -> None:
    from agent_eval_lab.calibrate.provisional import render_provisional_summary

    summary = render_provisional_summary(
        _fake_report(),
        models=["deepseek"],
        skipped=[],
        scored=14,
        errored=2,
    )
    assert "scored=14" in summary
    assert "errored=2" in summary


def test_render_provisional_summary_omits_counts_when_not_supplied() -> None:
    from agent_eval_lab.calibrate.provisional import render_provisional_summary

    summary = render_provisional_summary(
        _fake_report(),
        models=["deepseek"],
        skipped=[],
    )
    # No labeling line when counts not provided — backward compatible
    assert "scored=" not in summary
    assert "errored=" not in summary
