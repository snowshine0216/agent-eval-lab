"""EDGE: the F-domain candidate-edit run — the model actually fixes the repo.

The 009 `run_f` graded a single deterministic tree (the pinned base, or a stand-in
golden). This module wires the REAL eval the owner asked for: the candidate model
edits the pinned web-dossier checkout through pure file-edit tools (read_file /
list_files / str_replace / write_file over code-world state), and the held-out node
oracle grades the model's PRODUCED tree — preserving the model's real trajectory
(tokens / rounds / wall-time / cost), unlike `run_f`'s synthetic zero-usage path.

env-free (§4.1): no live infra. Each F task runs k INDEPENDENT model attempts
(D-set parity) — every attempt is valid (the node oracle is deterministic and
local), so there is no validity mask and no VOID. pass^k is then the fraction of
tasks whose k attempts ALL pass; efficiency totals are the honest sum over the k
attempts. The candidate base stays pinned at 5b0c13a6 (D32); m2021 HEAD is never
read. The held-out grading test is never seeded into the candidate tree (D19).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import httpx

from agent_eval_lab.datasets.f3_oracle import F3_TEST_REL, FAILURE_ANALYSIS_DIR
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult, is_env_invalid_run
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.f_run import CANDIDATE_BASE_SHA, prefix_candidate_tree
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
from agent_eval_lab.tasks.schema import Task, TaskInput
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply
from agent_eval_lab.tools.code_world import prefix_collision

# The edit tools the candidate gets (a subset of code-world): inspect + edit only.
# run_tests is deliberately EXCLUDED — F grades via the held-out node oracle, not
# the candidate running tests, and it would need an executor we never wire here.
F_EDIT_TOOL_NAMES: tuple[str, ...] = (
    "list_files",
    "read_file",
    "str_replace",
    "write_file",
)

_EDIT_SYSTEM = (
    "You are fixing code in a checked-out repository. Its files are already loaded "
    "into your workspace. You have exactly these tools: {tools}. Inspect files with "
    "list_files / read_file, then make the owner-specified change with str_replace "
    "(preferred — give enough surrounding context that old_str is unique) or "
    "write_file. Change ONLY what the task requires; leave every other file and "
    "layer untouched. Do not attempt to run tests. When the edit is complete, reply "
    "with a one-line summary and stop."
)

# Factor P — context-gathering prompt nudges (item 003 §B.3). A discrete,
# attributable block appended to _EDIT_SYSTEM on the `prompt` and `both` arms
# ONLY (gated by initial_state["factor_p"] in make_edit_task). Glossary: it says
# "visible tests", never "public tests" (§11.4). bare/feedback keep the
# unmodified _EDIT_SYSTEM.
_FACTOR_P_BLOCK = (
    "Before editing, gather context. Read the full body of any method that a call "
    "or assertion you touch depends on — do not assume its contract from its name. "
    "Before adding a method, read the sibling methods in the same file so your "
    "addition matches their shape and conventions. Read the local conventions for "
    "this layer (its README, config, or nearest CLAUDE.md) before you write. Read "
    "the entire target file and the full set of visible tests that exercise it "
    "before your first edit. Change only what the task requires; leave every other "
    "file and layer untouched."
)


def _git_show(repo: Path, rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{CANDIDATE_BASE_SHA}:{rel}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _f3_candidate_tree(task: Task, *, repo: Path) -> dict[str, str]:
    """The F3 candidate tree: the full failure-analysis layer at the pinned base
    SHA so the causal guard tests (correlate/signal/compose/index) run, plus the
    editable report-to-allure.js. The held-out golden grading test is NEVER seeded
    (D19) — the oracle overlays it at grade time."""
    tree: dict[str, str] = {"tests/wdio/package.json": '{"type":"module"}\n'}
    listing = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "ls-tree",
            "--name-only",
            "-r",
            CANDIDATE_BASE_SHA,
            "--",
            FAILURE_ANALYSIS_DIR,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for rel in listing:
        if not rel.endswith(".js"):
            continue
        if rel == F3_TEST_REL:
            continue  # held-out golden grading test — never candidate-visible (D19)
        tree[rel] = _git_show(repo, rel)
    return tree


def build_candidate_tree(task: Task, *, repo: Path) -> dict[str, str]:
    """Seed the candidate workspace at the pinned base SHA (D32).

    F1/F2 are self-contained in their target paths; F3 additionally needs the
    failure-analysis causal layer present so the held-out guard tests can run.

    Ablation arms (item 004 §B.5) additionally carry `initial_state['context_paths']`
    — a curated context set (siblings + readable source) materialized identically
    across all four arms from the pinned SHA so Factor P's read-the-context directives
    are non-vacuous. Production `build_f_tasks` sets no context_paths, so its trees
    stay minimal. The held-out golden grading test is never seeded (D19); the
    overlay-disjointness invariant (§10.4, seeded_held_out_disjoint) guarantees a
    context path can never collide with a held-out path.
    """
    if task.id == "f-f3" or task.id.startswith("f-f3-"):
        return _f3_candidate_tree(task, repo=repo)
    tree = dict(prefix_candidate_tree(task, repo=repo))
    for rel in (task.initial_state or {}).get("context_paths", ()):
        tree[rel] = _git_show(repo, rel)
    return tree


def seeded_held_out_disjoint(
    seeded_paths: Sequence[str], held_out_files: Mapping[str, str]
) -> bool:
    """True iff no seeded (candidate-visible) path collides with any held-out
    oracle path under `prefix_collision` (§10.4).

    Pure. The held-out node oracle overlays `held_out_files` over the candidate
    base tree at grade time; `overlay_node_oracle` raises NodeOverlayCollision ->
    `tree_collision` error if a seeded path canonically prefix-collides with a
    held-out path. Identical spellings are DISPLACEMENTS (overwrite allowed), not
    collisions, so they are disjoint. Reuses the project's single collision
    predicate (tools/code_world.prefix_collision) — never reimplemented."""
    return not any(
        prefix_collision(seeded, oracle)
        for seeded in seeded_paths
        for oracle in held_out_files
    )


def make_edit_task(task: Task, *, base_tree: Mapping[str, str]) -> Task:
    """Recast an F task as a code-world edit task: swap the prose `bash` tool for
    the pure file-edit tools and seed the produced tree into `files`. The held-out
    verification and task identity are preserved verbatim.

    Factor P (item 003 §B.3): if initial_state["factor_p"] is truthy, append the
    attributable _FACTOR_P_BLOCK to the rebuilt _EDIT_SYSTEM. Factor V (§B.2): if
    initial_state["factor_v"] is truthy, additionally offer the run_tests tool name
    (its executor is item 005 — make_f_run_fn binds executor=None and refuses to
    drive a live V arm until then)."""
    state = task.initial_state or {}
    system = _EDIT_SYSTEM.format(tools=", ".join(F_EDIT_TOOL_NAMES))
    if state.get("factor_p"):
        system = f"{system}\n\n{_FACTOR_P_BLOCK}"
    tools = F_EDIT_TOOL_NAMES + (("run_tests",) if state.get("factor_v") else ())
    user = next((m for m in task.input.messages if m.role == "user"), None)
    messages = (MessageTurn(role="system", content=system),) + (
        (user,) if user is not None else ()
    )
    initial_state = {**state, "files": dict(base_tree)}
    return replace(
        task,
        input=TaskInput(messages=messages, available_tools=tools),
        initial_state=initial_state,
    )


def make_f_run_fn(
    *,
    config: ProviderConfig,
    http_client: httpx.Client,
    temperature: float,
    max_tokens: int,
    condition_id: str,
    safety_cap: int = 60,
    max_rounds: int | None = None,
) -> Callable[[Task, int], Trajectory]:
    """Build the per-attempt model driver for one arm: run the code-world edit
    loop. The edit tools are pure (no executor in item 003); a V arm
    additionally declares the run_tests tool surface, but its sandboxed
    executor lands in item 005 — so this driver refuses to drive a live V arm
    until then (bare/prompt stay fully runnable)."""

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        # Factor V's executor + sandbox is item 005. A V arm declares run_tests
        # (its tool SURFACE) but has no executor here; driving it against the live
        # loop would silently run a no-op V loop, so refuse explicitly. bare/prompt
        # (factor_v falsey) stay fully runnable today.
        if (edit_task.initial_state or {}).get("factor_v"):
            raise NotImplementedError(
                "Factor V executor is item 005; cannot drive a V arm "
                f"({edit_task.id!r}) against a live provider in 003"
            )
        return run_single(
            task=edit_task,
            registry=CODE_WORLD_TOOLS,
            config=config,
            http_client=http_client,
            run_index=run_index,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=code_world_apply,
            executor=None,
            run_uid=f"{condition_id}__{edit_task.id}__{run_index:04d}",
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )

    return run_fn


def _grade(task: Task, trajectory: Trajectory, *, condition_id: str, run_index: int):
    verdicts = precompute_node_verdicts(
        verification=task.verification, trajectory=trajectory
    )
    grade = grade_trajectory(
        verification=task.verification,
        trajectory=trajectory,
        registry={},
        verdicts=verdicts,
    )
    return RunResult(
        task_id=task.id,
        condition_id=condition_id,
        run_index=run_index,
        trajectory=trajectory,
        grade=grade,
    )


def run_f_candidate(
    *,
    tasks: Sequence[Task],
    k: int,
    condition_id: str,
    build_tree_fn: Callable[[Task], Mapping[str, str]],
    run_fn: Callable[[Task, int], Trajectory],
) -> Iterator[ReplacementOutcome]:
    """Yield one ReplacementOutcome per F task: k independent model attempts, each
    graded on its OWN produced tree by the held-out node oracle.

    The node oracle is env-free, so a clean trial is always valid — BUT a provider
    HTTP rejection (`is_env_invalid_run`: a 403/429/empty-choices on the model call)
    is an env-invalidity, not a model failure: it is masked out of `valid_runs` and
    flagged invalid in `attempts`, and a task that lands fewer than k clean trials is
    VOID (never scored over <k, D34). `build_tree_fn`/`run_fn` are injected so unit
    tests need no provider/network."""
    for task in tasks:
        base_tree = build_tree_fn(task)
        edit_task = make_edit_task(task, base_tree=base_tree)
        runs = tuple(
            _grade(task, run_fn(edit_task, i), condition_id=condition_id, run_index=i)
            for i in range(k)
        )
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=not is_env_invalid_run(r), run=r)
            for i, r in enumerate(runs)
        )
        valid_runs = tuple(r for r in runs if not is_env_invalid_run(r))
        yield ReplacementOutcome(
            valid_runs=valid_runs, attempts=attempts, void=len(valid_runs) < k
        )
