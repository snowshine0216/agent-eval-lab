"""Assemble the F2 oracle verification (§4.1 / D24 / D31).

build_f2_verification(evaluator_store) returns the AllOf that build_f_tasks
attaches to the F2 task. The held-out F2 TEST is the only oracle file shipped
(plus the minimal tests/wdio/package.json); the golden wdio.conf.ts SOURCE is
never shipped — the candidate's produced conf is the source under test (D19).
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

F2_CONF_REL = "tests/wdio/wdio.conf.ts"
F2_TEST_REL = "tests/wdio/f2.held_out.test.js"
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/f2.held_out.test.js"


def build_f2_verification(evaluator_store: Path) -> AllOf:
    """Return the F2 AllOf: one NodeExecutionSpec running the held-out F2 test."""
    held_out_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F2_TEST_REL: held_out_test,
        },
        test_paths=(F2_TEST_REL,),
    )
    return AllOf(specs=(spec,))
