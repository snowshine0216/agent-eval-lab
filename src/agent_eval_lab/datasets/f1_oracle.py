"""Assemble the F1 oracle verification (§4.1 / D24 / D31).

build_f1_verification(evaluator_store) returns the AllOf that build_f_tasks
attaches to the F1 task. The held-out F1 TEST is read from the evaluator store
and shipped as the only oracle file (plus the minimal tests/wdio/package.json);
the golden SOURCE (the fixed spec/page-object) is never shipped — the candidate's
own produced files are the source under test. D19: nothing here writes into a
candidate-visible location.
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

F1_SPEC_REL = (
    "tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js"
)
F1_PAGE_REL = "tests/wdio/pageObjects/common/LibraryNotification.js"
F1_TEST_REL = "tests/wdio/f1.held_out.test.js"
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/f1.held_out.test.js"


def build_f1_verification(evaluator_store: Path) -> AllOf:
    """Return the F1 AllOf: one NodeExecutionSpec running the held-out F1 test."""
    held_out_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F1_TEST_REL: held_out_test,
        },
        test_paths=(F1_TEST_REL,),
    )
    return AllOf(specs=(spec,))
