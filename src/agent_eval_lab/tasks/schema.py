"""Task records and the VerificationSpec subset (spec §4.3-§4.4 + D-set §4.2)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.turns import MessageTurn


@dataclass(frozen=True, kw_only=True)
class ExpectedToolCall:
    """Spec-time tool call; call_id is unknowable when authoring."""

    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, kw_only=True)
class OutputMatchSpec:
    type: Literal["output_match"] = "output_match"
    expected_output: str
    normalizer: str | None = None


@dataclass(frozen=True, kw_only=True)
class ToolCallMatchSpec:
    type: Literal["tool_call_match"] = "tool_call_match"
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"


@dataclass(frozen=True, kw_only=True)
class StateEquals:
    type: Literal["state_equals"] = "state_equals"
    path: str
    expected: Any


@dataclass(frozen=True, kw_only=True)
class StateContains:
    type: Literal["state_contains"] = "state_contains"
    path: str
    expected: Any


StateConstraint = StateEquals | StateContains


@dataclass(frozen=True, kw_only=True)
class NoToolCall:
    type: Literal["no_tool_call"] = "no_tool_call"
    name: str


@dataclass(frozen=True, kw_only=True)
class OnlyModifies:
    type: Literal["only_modifies"] = "only_modifies"
    paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class MaxToolCalls:
    type: Literal["max_tool_calls"] = "max_tool_calls"
    n: int


TrajectoryConstraint = NoToolCall | OnlyModifies | MaxToolCalls


@dataclass(frozen=True, kw_only=True)
class FinalStateSpec:
    type: Literal["final_state"] = "final_state"
    constraints: tuple[StateConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class TrajectorySpec:
    type: Literal["trajectory"] = "trajectory"
    constraints: tuple[TrajectoryConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class AllOf:
    type: Literal["all_of"] = "all_of"
    specs: "tuple[VerificationSpec, ...]"


@dataclass(frozen=True, kw_only=True)
class LlmJudgeSpec:
    type: Literal["llm_judge"] = "llm_judge"
    rubric: str
    judge_model: str
    scale: tuple[int, int] = (1, 5)


@dataclass(frozen=True, kw_only=True)
class ExecutionSpec:
    """Tier-2 oracle tests: held-out files the agent never sees (ADR-0010).

    `held_out_tests` maps POSIX-relative path -> text content; `timeout_s`
    is the per-task sandbox budget (None => the edge's DEFAULT_TIMEOUT_S).
    No expected_status knob exists: pass means suite status == "passed".
    """

    type: Literal["execution"] = "execution"
    held_out_tests: Mapping[str, str]
    timeout_s: float | None = None


@dataclass(frozen=True, kw_only=True)
class NodeExecutionSpec:
    """Tier-2 oracle that runs `node --test` over a candidate-supplied base tree
    with evaluator-store test files overlaid oracle-wins (F3, §18.6 / D31).

    `held_out_files` maps POSIX-relative path -> text (the golden test file and
    a minimal `tests/wdio/package.json`); these overlay the caller's base_tree.
    `test_paths` are the POSIX-relative test files passed to `node --test`.
    `timeout_s` None => the node edge's DEFAULT_TIMEOUT_S.
    """

    type: Literal["node_execution"] = "node_execution"
    held_out_files: Mapping[str, str]
    test_paths: tuple[str, ...]
    timeout_s: float | None = None


@dataclass(frozen=True, kw_only=True)
class FactKeySpec:
    """Deterministic D-set L1-L3 oracle (§4.2 / D18 / D24).

    required: literal substrings that MUST appear in the candidate's answer AND
      in page_snapshot (the faithfulness gate: a stated fact must be on the page).
    forbidden: contradiction substrings that must be ABSENT from the answer
      (e.g. a wrong version number = a hallucination).
    page_snapshot: the evaluator-frozen page text the answer is graded against
      (D36 snapshot); page_snapshot_sha256 records its content hash.
    level: the question's level (1-5); informs reporting, not the pass rule.

    Matching is case-insensitive, whitespace-normalized literal substring
    (graders/fact_key.py). No regex — keys stay owner-auditable.
    """

    type: Literal["fact_key"] = "fact_key"
    required: tuple[str, ...]
    forbidden: tuple[str, ...]
    page_snapshot: str
    page_snapshot_sha256: str
    level: int


@dataclass(frozen=True, kw_only=True)
class ReadbackSpec:
    """B-set readback oracle (§18.7 / D24). The grader compares a ReadbackResult
    (evaluator-credentialed playwright-cli readback of the captured object) to a
    held-out golden. Three golden-discriminating checks: (1) the captured object
    exists; (2) definition matches (cube == expected_cube, rows superset of
    required_rows, columns superset of required_columns, prompt == expected_prompt);
    (3) the executed grid equals the golden grid under prompt = expected_prompt.

    The golden grid lives in the evaluator-only store, NOT in this spec text —
    `golden_grid` is loaded from the gitignored fixture by the builder, never
    authored into a tracked source file (D19)."""

    type: Literal["readback"] = "readback"
    expected_cube: str
    required_rows: tuple[str, ...]
    required_columns: tuple[str, ...]
    expected_prompt: str
    golden_grid: tuple[tuple[str, ...], ...]


# The complete tagged union: deterministic tiers (Weeks 1-4), the Tier-3
# model-based judge (item 003), the Tier-2 execution oracle (Weeks 5-6),
# the Tier-2 node execution oracle (Weeks 7-10, F3), the D-set
# fact-key oracle (item 005 §4.2), and the B-set readback oracle (item 010 §18.7).
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
    | ExecutionSpec
    | NodeExecutionSpec
    | FactKeySpec
    | ReadbackSpec
)


@dataclass(frozen=True, kw_only=True)
class TaskInput:
    messages: tuple[MessageTurn, ...]
    available_tools: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: Literal["dev", "held_out"]
    version: str
    provenance: str
    world_template_id: str | None = None
    difficulty_knob: str | None = None
    max_steps: int | None = None
    max_rounds: int | None = None
    review: str | None = None


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = None
