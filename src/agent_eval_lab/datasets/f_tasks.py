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
from agent_eval_lab.tasks.schema import Task, TaskInput, TaskMetadata

_CANDIDATE_BASE_SHA = "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505"

_SYSTEM = (
    "You are fixing a flaky end-to-end test in the web-dossier wdio suite. You have "
    "a single tool: `bash`. The repo is checked out at a frozen base commit. Make the "
    "owner-specified change, leaving all other layers untouched."
)

_F1_SPEC = (
    "tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js"
)
_F1_USER = (
    f"In {_F1_SPEC}, test case [TC99396_10] asserts on a non-deterministic "
    "error notification via a flaky image comparison (takeScreenshotByElement). "
    "Replace the image comparison with a deterministic wait on the NAMED snapshot "
    "reaching a terminal state (ready or error), adding a "
    "waitForSnapshotFinalNotificationByName(name) helper to "
    "tests/wdio/pageObjects/common/LibraryNotification.js."
)
_F2_USER = (
    "In tests/wdio/wdio.conf.ts, runFailureAnalysisEngine discards the "
    "failure-analysis engine result. Capture it and print a terminal diagnose "
    "trace: log only failed (non-2XX) requests under "
    "'[DiagTrace] Failed requests:', then log "
    "'[DiagTrace] signal=<signal> confidence=<confidence>' from the engine "
    "result. Guard the whole trace so a logging error never breaks "
    "afterTest/afterHook."
)
_F3_USER = (
    "In tests/wdio/utils/failure-analysis/report-to-allure.js, the network "
    "attachment lists every request. Surface only failed (non-2XX) requests so "
    "a 503 is not buried under hundreds of 200s, and emit no network attachment "
    "when all requests succeed."
)


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
