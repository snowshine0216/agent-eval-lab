"""Assemble the 3 F-domain Tasks (§4.1): each web-dossier repo fix paired with its
held-out node oracle. Mirrors datasets/cmc_dset.build_cmc_tasks (the D builder).

The candidate-visible TaskInput describes the fix in prose; the held-out ORACLE
(the node test) is read by the per-fix build_fN_verification from the
permission-isolated evaluator store (D19/D33). initial_state pins the candidate
base SHA (5b0c13a6, D32) and the repo-relative target paths so the F runner can
reconstruct the candidate workspace without ever touching m2021 HEAD.
"""

from pathlib import Path

from agent_eval_lab.datasets.f1_oracle import (
    F1_PAGE_REL,
    F1_SPEC_REL,
    build_f1_verification,
)
from agent_eval_lab.datasets.f2_oracle import F2_CONF_REL, build_f2_verification
from agent_eval_lab.datasets.f3_oracle import F3_SOURCE_REL, build_f3_verification
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.f_run import CANDIDATE_BASE_SHA as _CANDIDATE_BASE_SHA
from agent_eval_lab.tasks.schema import Task, TaskInput, TaskMetadata

_SYSTEM = (
    "You are fixing a flaky end-to-end test in the web-dossier wdio suite. You have "
    "a single tool: `bash`. The repo is checked out at a frozen base commit. Make the "
    "owner-specified change, leaving all other layers untouched."
)

_F1_SPEC = (
    "tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js"
)
_F1_USER = (
    f"In {_F1_SPEC}, test case [TC99396_10] verifies the error notification for "
    "a prompted-document snapshot sent to background. The assertion currently "
    "uses a pixel-level image comparison that fails nondeterministically across "
    "environments. Replace it with a deterministic, content-based assertion that "
    "confirms the expected notification has appeared for that specific document. "
    "You may need to add a helper method to "
    "tests/wdio/pageObjects/common/LibraryNotification.js."
)
_F2_USER = (
    "In tests/wdio/wdio.conf.ts, the failure-analysis engine is invoked on test "
    "failure but its result is discarded. Extend runFailureAnalysisEngine so that, "
    "after the engine finishes, a brief diagnostic summary is printed to the "
    "terminal to aid triage. The summary should surface the failed (non-2XX) "
    "network requests recorded during the test and the engine's assessment of the "
    "failure. Guard the whole block so a logging error never breaks "
    "afterTest/afterHook."
)
_F3_USER = (
    "In tests/wdio/utils/failure-analysis/report-to-allure.js, the Allure "
    "network attachment currently lists every request captured during the test. "
    "This makes it hard to spot real errors when a page fires hundreds of "
    "successful requests. Change the attachment so it highlights only the "
    "requests that indicate a problem, and skip the attachment entirely when "
    "there are no such requests."
)


# Curated context sets (item 004 §B.5/§C) — additional paths seeded into the
# ABLATION-arm candidate trees beyond target_paths, read identically across all
# four arms from the pinned base SHA (5b0c13a6; m2021 never read). Production
# build_f_tasks seeds none. Each path excludes the held-out golden (D19) and any
# visible test that asserts the discriminating behavior (§11.6).
_F1_CONTEXT_PATHS: tuple[str, ...] = (
    # small sibling page-objects that surface the waitFor*({timeout,timeoutMsg})
    # convention; the throw-on-timeout golden stays held-out.
    "tests/wdio/pageObjects/common/Alert.js",
    "tests/wdio/pageObjects/common/SearchBox.js",
    "tests/wdio/pageObjects/common/Panel.js",
)
_F2_CONTEXT_PATHS: tuple[str, ...] = (
    # analyzeFailure's source so its {signal, confidence} return shape is readable
    # from the source; the two tests that ASSERT the split are excluded.
    "tests/wdio/utils/failure-analysis/index.js",
)
# F3's tree is already broad (_f3_candidate_tree seeds the whole causal layer
# minus F3_TEST_REL); no seeded test asserts the cap+summary, so no new context.
_F3_CONTEXT_PATHS: tuple[str, ...] = ()

# Arm -> (factor_p, factor_v) — the 2x2 (spec item 003 §B.1).
_ARM_FACTORS: dict[str, tuple[bool, bool]] = {
    "bare": (False, False),
    "prompt": (True, False),
    "feedback": (False, True),
    "both": (True, True),
}

# Factor V's tool name. The executor that binds it is item 005; here it only
# records the V arms' tool SURFACE (their identity). bare/prompt never see it.
_V_TOOL = "run_tests"

# The F-ablation runs every arm under a uniform 40-round cap (§B.1); production F
# stays 20. The value is FROZEN in item 006's f_ablation_spec — here it only makes
# the per-task max_rounds override path reachable (resolve_max_rounds honors it).
_ABLATION_MAX_ROUNDS = 40


def _task(
    *, task_id: str, user: str, verification, target_paths: tuple[str, ...]
) -> Task:
    return Task(
        id=task_id,
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content=_SYSTEM),
                MessageTurn(role="user", content=user),
            ),
            available_tools=("bash",),
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="f-domain-v1",
            provenance="web-dossier PR #23483 (pre-fix 5b0c13a6)",
        ),
        initial_state={
            "repo": "web-dossier",
            "candidate_base_sha": _CANDIDATE_BASE_SHA,
            "target_paths": target_paths,
        },
    )


def _arm(
    *,
    base: str,
    arm: str,
    user: str,
    verification,
    target_paths: tuple[str, ...],
    context_paths: tuple[str, ...],
) -> Task:
    """One arm-task of a base F task: same held-out verification + same
    tree-driving initial_state as its three siblings, differing only in the
    factor_p/factor_v flags (read by make_edit_task) and available_tools.

    initial_state carries `context_paths` (item 004 §B.5) — the curated context
    set seeded identically across all four arms by build_candidate_tree."""
    factor_p, factor_v = _ARM_FACTORS[arm]
    tools = ("bash", _V_TOOL) if factor_v else ("bash",)
    return Task(
        id=f"f-{base}-{arm}",
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content=_SYSTEM),
                MessageTurn(role="user", content=user),
            ),
            available_tools=tools,
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="f-domain-v1",
            provenance="web-dossier PR #23483 (pre-fix 5b0c13a6)",
            max_rounds=_ABLATION_MAX_ROUNDS,
        ),
        initial_state={
            "repo": "web-dossier",
            "candidate_base_sha": _CANDIDATE_BASE_SHA,
            "target_paths": target_paths,
            "context_paths": context_paths,
            "factor_p": factor_p,
            "factor_v": factor_v,
        },
    )


def build_f_tasks(*, evaluator_store: Path) -> tuple[Task, ...]:
    return (
        _task(
            task_id="f-f1",
            user=_F1_USER,
            verification=build_f1_verification(evaluator_store),
            target_paths=(F1_SPEC_REL, F1_PAGE_REL),
        ),
        _task(
            task_id="f-f2",
            user=_F2_USER,
            verification=build_f2_verification(evaluator_store),
            target_paths=(F2_CONF_REL,),
        ),
        _task(
            task_id="f-f3",
            user=_F3_USER,
            verification=build_f3_verification(evaluator_store),
            target_paths=(F3_SOURCE_REL,),
        ),
    )


def build_f_task_arms(*, evaluator_store: Path) -> tuple[Task, ...]:
    """The 12 F task-arms (3 base tasks x 4 arms) for the harness-factor ablation
    (item 003 §B.1). Each base's four arms share that base's held-out
    VerificationSpec and tree-driving initial_state byte-for-byte — including the
    curated context_paths (item 004 §B.5) — and differ ONLY in Factor P (a
    system-prompt block, gated by initial_state['factor_p']) and Factor V (the
    declared tool surface, initial_state['factor_v'] + available_tools). The arm
    IS the task_id — no arm_id, no spec change."""
    bases = (
        (
            "f1",
            _F1_USER,
            build_f1_verification(evaluator_store),
            (F1_SPEC_REL, F1_PAGE_REL),
            _F1_CONTEXT_PATHS,
        ),
        (
            "f2",
            _F2_USER,
            build_f2_verification(evaluator_store),
            (F2_CONF_REL,),
            _F2_CONTEXT_PATHS,
        ),
        (
            "f3",
            _F3_USER,
            build_f3_verification(evaluator_store),
            (F3_SOURCE_REL,),
            _F3_CONTEXT_PATHS,
        ),
    )
    return tuple(
        _arm(
            base=base,
            arm=arm,
            user=user,
            verification=verification,
            target_paths=paths,
            context_paths=context_paths,
        )
        for base, user, verification, paths, context_paths in bases
        for arm in ("bare", "prompt", "feedback", "both")
    )
