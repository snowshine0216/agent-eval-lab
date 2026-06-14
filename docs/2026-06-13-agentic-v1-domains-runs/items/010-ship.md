PR: https://github.com/snowshine0216/agent-eval-lab/pull/21
Mode: A
Branch: feat/agentic-v1-010-b-domain-m2
Base: main
Title: feat(agentic-v1): B-domain adapter — readback oracle + M2 skill-effect machinery (010)

## Ship path
Tier-2 (orchestrator-driven `gh pr create`), not `/ship` — same rationale as 008/009
(repo convention is plain gh squash PRs; no VERSION file; flaky oracle-subprocess
suite). Per ship.md tier-2 contract: the review verdict is produced by a dispatched
Sonnet review subagent (`items/010-review.md`); `/code-review` is the independent
second pass (`items/010-pr-review.md`). Both gate the merge. Protected-base merge to
`main` opt-in was GRANTED by the user this turn ("Squash-merge to main").

## Doc-sync done in ship
- CHANGELOG.md `[Unreleased]` gained a "B-domain adapter + M2 skill-effect machinery
  (item 010)" subsection (commit on branch).

## Pre-ship integrity verification (orchestrator, before push)
- Complete-token `git grep` over the tracked tree using the REAL gitignored
  `evaluator.toml` values: the golden object id, project id, golden grid, MSTR host,
  and store/skill paths each return **0** tracked-file matches. The only grep hits
  were false positives — `playwright-cli` (public tool name), `mstr1` (generic MSTR
  Tutorial default username, docs-only), and a 6-char default password that
  coincidentally appears as a substring of the hex alphabet `"0123456789abcdef"` in
  two pre-existing test files untouched by 010. No golden/answer leak in 010's diff.
- `evaluator-only/b-set-golden/*.json` confirmed gitignored + unstaged.

## Drift
- `items/010-drift.md` Verdict: PASS (10/10 plan tasks; 2 deviations accepted:
  CandidateConfig.url optional — plan amended `bccd719`; 3 dependent fixtures updated).

## Live runs
- DEFERRED. This PR lands the deterministic machinery only; the live readback + the
  M2 arm execution are in the owner's `EXECUTE-DEFERRED.md` runbook.
