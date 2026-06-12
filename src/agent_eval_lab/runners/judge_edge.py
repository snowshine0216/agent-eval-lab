"""EDGE: the single judge I/O boundary (ADR 0005).

Builds the prompt (pure), calls the existing OpenAI-compatible client, parses the
reply (pure), and stamps judge_model + prompt_hash onto the verdict. A transport,
HTTP, empty-response, or parse failure is captured as a serializable JudgeError —
an exception NEVER escapes into the verdict map (D2).
"""

from dataclasses import dataclass, replace
from typing import Literal

import httpx

from agent_eval_lab.graders.judge import (
    JudgeParseFailure,
    JudgeVerdict,
    build_judge_prompt,
    parse_judge_response,
    prompt_hash,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.tasks.schema import LlmJudgeSpec


@dataclass(frozen=True, kw_only=True)
class JudgeError:
    kind: Literal["transport", "http", "parse", "empty_response"]
    error: str
    prompt_hash: str
    judge_model: str


def run_judge(
    *,
    spec: LlmJudgeSpec,
    trajectory: Trajectory,
    config: ProviderConfig,
    http_client: httpx.Client,
) -> JudgeVerdict | JudgeError:
    messages = build_judge_prompt(spec=spec, trajectory=trajectory)
    p_hash = prompt_hash(messages)
    model = condition_id(config)
    try:
        response = chat_completion(
            config=config,
            messages=messages,
            tools=(),
            temperature=0.0,
            max_tokens=2048,  # judge responses are short (score + rationale)
            http_client=http_client,
        )
    except httpx.HTTPStatusError as exc:
        return JudgeError(
            kind="http", error=str(exc), prompt_hash=p_hash, judge_model=model
        )
    except httpx.TransportError as exc:
        return JudgeError(
            kind="transport", error=str(exc), prompt_hash=p_hash, judge_model=model
        )
    choices = response.payload.get("choices") or []
    if not choices:
        return JudgeError(
            kind="empty_response",
            error="no choices in provider response",
            prompt_hash=p_hash,
            judge_model=model,
        )
    text = (choices[0].get("message", {}) or {}).get("content") or ""
    parsed = parse_judge_response(text, scale=spec.scale)
    if isinstance(parsed, JudgeParseFailure):
        return JudgeError(
            kind="parse", error=parsed.error, prompt_hash=p_hash, judge_model=model
        )
    return replace(parsed, judge_model=model, prompt_hash=p_hash)
