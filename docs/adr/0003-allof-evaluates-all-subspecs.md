# AllOf evaluates every sub-spec (no short-circuit) and reports the first failure's reason

`AllOf` grades by evaluating *all* of its sub-specs in declared order — it does
**not** short-circuit on the first failure. `passed` is the logical AND of every
sub-result; `failure_reason` is taken from the *first failing* sub-spec in
declared order; `evidence` carries the ordered list of *every* sub-result
(passed and failed); `score` is all-or-nothing (`1.0` iff passed else `0.0`).

## Considered Options

- **Evaluate all, report first failure** (chosen). A reader of a conjunction
  expects short-circuit, but we deliberately deviate: the failure taxonomy and
  the JD#4 audit trail need to see *every* sub-result, not just the first one
  that tripped. Reporting the first failure's `failure_reason` keeps the headline
  category deterministic and matches how an author reads declared order as
  priority.
- **Short-circuit on first failure.** Rejected: cheaper, but throws away the
  evidence of later sub-results, blinding the failure-mode report to co-occurring
  breaches (e.g. both a forbidden action *and* a step-limit overflow in one run).

## Consequences

Grading cost is the sum over all sub-specs regardless of early failure — bounded
and linear, acceptable for the deterministic tier. The first-failure rule is the
single source of the composite's `failure_reason`; consumers wanting the full
picture read `evidence`. Recursive nesting (`AllOf` within `AllOf`) inherits the
same semantics.
