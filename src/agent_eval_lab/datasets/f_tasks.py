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
