"""Assemble the F3 oracle verification (§18.6 / §4.1 / D31).

build_f3_verification(evaluator_store) returns the AllOf item 004 attaches to
the F3 task. The golden TEST file is read from the evaluator store and shipped
as a held-out oracle file; the golden SOURCE is never included (the candidate's
own report-to-allure.js is the source under test). D19: nothing here writes into
a candidate-visible location.
"""

from pathlib import Path

from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

FAILURE_ANALYSIS_DIR = "tests/wdio/utils/failure-analysis"
F3_SOURCE_REL = f"{FAILURE_ANALYSIS_DIR}/report-to-allure.js"
F3_TEST_REL = f"{FAILURE_ANALYSIS_DIR}/__tests__/report-to-allure.test.js"
CAUSAL_TEST_RELS = tuple(
    f"{FAILURE_ANALYSIS_DIR}/__tests__/{n}"
    for n in ("correlate.test.js", "signal.test.js", "compose.test.js", "index.test.js")
)
WDIO_PKG_REL = "tests/wdio/package.json"
WDIO_PKG_CONTENT = '{"type":"module"}\n'

_GOLDEN_TEST_REL = "golden-files/report-to-allure.test.js.golden"


def build_f3_verification(evaluator_store: Path) -> AllOf:
    """Return the F3 AllOf: golden attachment test + causal-layer guard."""
    golden_test = (evaluator_store / _GOLDEN_TEST_REL).read_text(encoding="utf-8")
    f3_spec = NodeExecutionSpec(
        held_out_files={
            WDIO_PKG_REL: WDIO_PKG_CONTENT,
            F3_TEST_REL: golden_test,
        },
        test_paths=(F3_TEST_REL,),
    )
    causal_spec = NodeExecutionSpec(
        held_out_files={WDIO_PKG_REL: WDIO_PKG_CONTENT},
        test_paths=CAUSAL_TEST_RELS,
    )
    return AllOf(specs=(f3_spec, causal_spec))
