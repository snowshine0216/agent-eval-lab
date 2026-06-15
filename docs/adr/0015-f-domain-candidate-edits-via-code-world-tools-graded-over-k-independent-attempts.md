# F-domain candidate edits via code-world tools, graded over k independent attempts

The 009 F-domain runner (`runners/f_run.py`) graded a single *deterministic* file
tree: `run_m1`'s F branch called `prefix_candidate_tree` (the pinned base) and
`_grade_tree` wrapped it in a synthetic, zero-usage `Trajectory`, replicated to
`k` identical runs. That was a stand-in — the model never ran, so it could not
measure the candidate's code-modification capability (the whole point of the
F-domain). `EXECUTE-DEFERRED.md` §2 framed the live F run as "the candidate
produces a file tree, the node oracle grades it" but left the producer unbuilt.

`runners/f_candidate.py` builds that producer. The candidate model edits the
pinned `web-dossier` checkout and the held-out node oracle grades the model's
**real** trajectory, preserving its tokens / rounds / wall-time / cost.

## Considered Options

- **Edit via code-world tools (`read_file` / `list_files` / `str_replace` /
  `write_file`) over in-state `files`** (chosen). The F task prose says "single
  tool: bash", but the existing `bash_edge` allows only `playwright-cli` (it is
  the D/B-set browse boundary), so no general file-editing bash exists; building
  one would add subprocess-sandboxing surface for no grading benefit, since the
  oracle reads the produced *tree*, not a shell transcript. The code-world tools
  are pure, already tested, and env-free — the model reads and edits files and
  the loop threads the edited tree into `final_state["files"]`, exactly what
  `precompute_node_verdicts` grades. A new `str_replace` tool (single unique
  occurrence) was added so large files (e.g. the 37 KB `wdio.conf.ts`) are edited
  in place rather than rewritten whole — measuring *fixing*, not transcription,
  and avoiding `max_tokens` truncation of a full-file rewrite.
- **Build a general file-editing bash executor.** Rejected: more I/O-sandbox
  surface, flakier, and the oracle never inspects shell output — only the tree.
- **Keep `run_f`'s single-artifact-graded-k-identical shape with a real model.**
  Rejected: `efficiency_summary` *sums* tokens and `condition_cost_usd` sums cost
  across valid runs, so replicating one real attempt `k`× would misreport F
  tokens/cost as `k`× the true usage. The synthetic zero-usage path hid this; a
  real model exposes it.

- **k INDEPENDENT model attempts per F task** (chosen, D-set parity). Each task
  runs `k` separate attempts; `pass^k` is the fraction of tasks whose `k` attempts
  *all* pass (genuine reliability, not `pass^1`), and the summed efficiency totals
  are the honest cost of the `k` attempts — consistent with how D aggregates.
  F is env-free, so every attempt is valid: there is no validity mask, no
  replacement loop, and no VOID (contrast `run_dset`'s D34 path).

## Consequences

F now measures real code-modification capability per arm. The `binomial_exact`
CI (frozen spec) is over the 3 F tasks; with only 3 tasks it is wide — honest,
not a defect. Determinism caveat: cloud providers are not bit-reproducible even
at `temperature=0`, so `pass^k` carries genuine attempt-to-attempt variance
(that is the metric, not noise to suppress). The held-out grading test is never
seeded into the candidate tree (D19); the base stays pinned at `5b0c13a6` and
`m2021` HEAD is never read (D32). The F1/F2 candidate trees are their target
paths; F3 additionally seeds the full `failure-analysis` causal layer at the base
SHA so the guard tests (`correlate`/`signal`/`compose`/`index`) run. The arm is
driven by a standalone `run-f` CLI command (run-dset parity) so F runs without
re-triggering the live D-set. `str_replace` lives in `tools/code_world.py` and is
available to any code-world task that lists it (`code_repair` does not).
