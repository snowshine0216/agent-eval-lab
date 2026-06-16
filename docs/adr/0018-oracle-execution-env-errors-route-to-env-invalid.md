# Oracle-execution env errors route to env-invalid (defense-in-depth)

`is_env_invalid_run` (records/grade.py) originally keyed env-invalidity on ONE
source: a PROVIDER-side failure recorded on the trajectory — a `chat_completion`
HTTP rejection (`PROVIDER_ERROR`) or empty `choices` (`NO_CHOICES_ERROR`). That
covers "the model never got a fair trial because the provider refused", but not
"the model never got a fair trial because the GRADING ORACLE could not run".

The F3 held-out oracle runs `node --test --test-reporter=junit` (runners/node_edge.py).
On node < 20 the `--test-reporter` flag is rejected (`node: bad option`, exit code
9), so node parses zero tests and `node_suite_status` classifies the run
`status="error"`. The pure grader then scored it `passed=False, failure_reason=None`
— an ordinary model FAIL — and `is_env_invalid_run` (looking only at the trajectory)
never saw it. In the f-ablation-v2 run this silently scored 180 attempts 0/180:
the *environment* could not run the oracle, but every attempt was charged to the
model (see reports/agentic-v1/f-ablation-v2/INCIDENT-node-v16.md).

The intended first line of defense is a fail-fast guard in the F CLI commands
(`node_supports_junit()`, runners/node_edge.py) that refuses before any paid call.
This ADR records the deeper, defense-in-depth layer that holds even if such a guard
is absent or bypassed: an incapable-node / oracle-execution error is loudly excluded
from `pass^k` rather than silently counted as a model failure. The two layers are
independent — this one lives in the pure grader + classifier, never the CLI.

## Considered Options

- **A grader self-declares env-invalidity via an `env_invalid` evidence marker;
  the classifier ORs it with the provider-side signal** (chosen). The pure node
  grader detects the two oracle-can't-run cases — an incapable node
  (`is_incapable_node_result`: `status="error"` + `exit_code == 9` + zero tests)
  and a `NodeExecutionError(kind="harness")` (node binary missing / OSError
  launching the subprocess) — and stamps `evidence["env_invalid"] = True` with an
  `env_invalid_reason`. `is_env_invalid_run` returns True when EITHER the
  trajectory carries a provider error OR the grade carries the marker. The marker
  is domain-neutral: any grader can set it, so the classifier stays generic.
- **String-match the oracle's stderr in the classifier.** Rejected: brittle
  (wording is localized and version-specific) and it pushes node-specific knowledge
  into the generic, domain-agnostic classifier. Exit code 9 is node's stable
  invalid-argument contract; the grader (which already holds the `ExecutionResult`)
  is the right place to interpret it.
- **Broaden the `SuiteStatus` literal with an `env_error` value.** Rejected:
  `SuiteStatus` is shared with the pytest oracle; a new value ripples into every
  status switch for no benefit. The marker rides the evidence, not the status.
- **Treat EVERY `status="error"` as env-invalid.** Rejected: a model that breaks
  the code under a *capable* node yields `status="error"` with `exit_code 1` (an
  import/load crash) — a real model FAIL. Only node's own CLI-parser rejection
  (exit 9, reachable solely from the harness's flags, never from user code inside
  an already-started runner) is the environment's fault. `tree_collision` and
  `verdict_missing` are model/wiring faults and likewise stay plain non-passes.

## Consequences

Env-invalidity now spans two independent sources — provider-side (trajectory) and
oracle-side (grade) — and `is_env_invalid_run` is the single OR over them. Because
real F verifications wrap their `NodeExecutionSpec`(s) in an `AllOf` (and F3 has
two), the grader's marker lands NESTED under `evidence['sub_results'][*]['evidence']`
(composite.py); the classifier therefore recurses the whole evidence tree to find
it. This nesting is exactly why the incident stayed silent, so the recursion is
load-bearing, not incidental — if any sub-grade could not run, the whole run is
masked (a partial oracle grade is untrustworthy).

This refines ADR-0015's "F is env-free, so … no VOID": an incapable node or an
oracle exec error DOES mask and can VOID an F task (fewer than k clean trials →
VOID, D34). The fail-fast guards remain the first line of defense; this layer is
the backstop. No D/B-set behavior changes — those graders never set the marker, so
the classifier's extra branch is inert for them.
