# code_repair_v1 — capability taxonomy

The code_repair_v1 set (`examples/datasets/code_repair_v1.jsonl`, 15 tasks) is the
first dataset on the code-world: each task is a small broken Python program the
agent repairs with `read_file` / `write_file` / `list_files` / `run_tests`, graded
by held-out **oracle tests** through the production oracle edge (ADR-0010/0011),
with oracle paths disjoint from the visible tests and breadth proven mechanically
(ADR-0012). Capabilities split by **evidence source** (what tells the agent where
the bug is); fix *shape* (single-line vs multi-hunk vs cross-file) is a difficulty
mechanism and lives in the knob vocabulary — preserving the v2
capability/knob/tier orthogonality.

## Capabilities × evidence source × verification shape

| capability | isolated skill (evidence source) | verification shape | tasks |
|------------|----------------------------------|--------------------|-------|
| `visible_test_localization` | a failing visible test names the symptom; map it to the fault | `execution` | cr-001, cr-002, cr-005, cr-012 |
| `prose_localization` | no visible tests at all (`no_tests`); the bug exists only as a prose report | `execution` (+ policy leg on cr-009) | cr-008, cr-009 |
| `test_comprehension` | the contract is specified *only* by the visible tests; prose never states the rule | `execution` | cr-003, cr-004 |
| `cross_file_repair` | the symptom surfaces in a different file than the fault | `execution` | cr-006, cr-007 |
| `regression_preservation` | the tempting fix breaks behavior only the oracle's regression tests protect | `execution` (+ `max_tool_calls` on cr-014) | cr-010, cr-014 |
| `overfit_resistance` | the visible tests underdetermine the fix; the oracle is strictly broader (hack fixture proves it) | `execution` (+ `no_tool_call` on cr-013) | cr-011, cr-013, cr-015 |

## Tiers × expected-failure rationale

| tier | count | % | expected-failure rationale |
|------|-------|---|----------------------------|
| T1 sanity | 2 | 13% | Every frontier model repairs these one-line faults — the regression floor. A T1 failure indicts the harness or world wiring (item 004's classifier needs this separability), not the model. |
| T2 moderate | 4 | 27% | Occasional misses on tests-as-spec comprehension and the first cross-file hop. The visible gradient between floor and hard band. |
| T3 hard | 6 | 40% | Prose-only localization, two-import fault distance, distractor files, regression traps. **Strong models are expected to sometimes fail here** — wrong-file edits and visible-suite-only fixes that the oracle rejects. |
| T4 adversarial | 3 | 20% | Designed so ≥ 1 frontier model is expected to fail: multi-hunk repair under a no-run-tests policy, aliasing repair under a tool-call budget, and an overfit trap whose visible suite is deliberately narrow. |

T3 + T4 = 9 / 15 = **60%** (the hard-majority directive).

## Difficulty knobs (closed code dialect)

Declared by every T3/T4 task in `metadata.difficulty_knob`; the workspace dialect
names do not transfer (per-world dialects, CONTEXT.md **Difficulty knob**).

- `fault_distance` — the symptom and the fault are separated by ≥ 2 import hops (cr-007).
- `multi_hunk` — the defect is several related edits; a partial fix still fails (cr-013).
- `oracle_breadth` — the visible tests underdetermine the fix; only the held-out oracle pins it (cr-010, cr-011, cr-015).
- `spec_obliqueness` — no failing visible test; the contract arrives as oblique prose (cr-008, cr-009).
- `constraint_budget` — a policy leg (`TrajectorySpec`) budgets or forbids tool use (cr-014).
- `distractor_file` — a correct file plausibly looks at fault; the oracle regression-pins it (cr-012).

## Bug classes (closed vocabulary, sidecar + ledger only)

`off_by_one`, `logic_inversion`, `exception_handling`, `type_coercion`,
`boundary_condition`, `aliasing_mutation` — every task tags exactly one primary
class in `code_repair_v1_review_fixtures.json`; every class is represented.
`TaskMetadata` is unchanged (the v2 sidecar precedent).

## Determinism

Every program and test is pure stdlib computation: no clock, RNG, network, env,
filesystem, or subprocess surface — enforced mechanically by the 15-module import
banlist (`socket`, `http`, `urllib`, `requests`, `subprocess`, `multiprocessing`,
`threading`, `asyncio`, `random`, `secrets`, `uuid`, `time`, `datetime`, `os`,
`tempfile`) in `tests/datasets/test_code_repair_v1.py`. Dates in fixtures are
literal ISO strings compared lexicographically. Same task + same final tree ⇒
byte-identical verdict (proven by the determinism spot-check).
