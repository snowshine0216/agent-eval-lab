# B-set grid grading treats data-row order as non-significant

The B-1 readback oracle's grid check (§18.7/D24) must answer "does the executed
grid carry the golden's CONTENT" — but a MicroStrategy executed grid does not
guarantee a stable data-row order run-to-run, so the strict positional
`result_grid == golden_grid` equality shipped in item 010's first cut false-FAILs
a correct candidate purely on row permutation (the oracle false-negative the 010
fix loop logged as F2). `_grid_matches` (`datasets/b1_oracle.py`) therefore
compares the **header row (row 0) positionally** and the **data rows (rows 1+) as
an order-insensitive multiset** — `sorted(result_grid[1:]) == sorted(golden_grid[1:])`
on both sides — with an empty grid matching only the empty grid.

## Considered Options

- **Header-positional, data-rows-as-sorted-multiset** (chosen). B-1's task
  specifies the cube / rows / columns / prompt and the cell CONTENT, never a row
  ORDER; grading the data rows over content removes the only nondeterministic
  axis while leaving every golden-discriminating signal intact. Tuples of strings
  sort lexicographically on full row content, so any wrong cell value lands the
  row at a different sorted position — the multiset still differs.
- **Strict positional equality** (item 010's first cut). Rejected: false-FAILs a
  correct candidate whenever MSTR returns the same rows in a different order — a
  discriminativeness-corrupting false-negative, not a real miss.
- **Sort the header row too.** Rejected: the header carries column identity by
  position, so sorting it would let a column-permuted grid pass — weakening the
  definition check rather than the irrelevant axis.

## Consequences

The oracle cannot detect a row-ORDER requirement — accepted, because B-1 declares
none; a future B-task that makes row order significant would need its own
order-sensitive grid path (this decision is scoped to content-graded readback).
Discrimination is preserved: wrong VALUES change the sorted multiset, so
golden ⇒ PASS while wrong cube / missing required row / missing Cost column /
wrong prompt / altered cell ⇒ FAIL (the D24 negative fixtures still hold). The
header row stays positional, so a swapped header still FAILs. The semantics live
in `_grid_matches`; making data-row order significant again is a grading-semantics
change to the B-set oracle, not a bug fix.
