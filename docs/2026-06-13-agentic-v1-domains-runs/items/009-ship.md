PR: https://github.com/snowshine0216/agent-eval-lab/pull/19
Mode: A
Branch: feat/agentic-v1-009-f-domain
Base: main
Title: feat(agentic-v1): F-domain repo adapter — F1/F2 env-free oracles + run-m1 wiring (009)

## Ship path
Tier-2 (orchestrator-driven `gh pr create`), not `/ship` — same rationale as 008
(repo convention is plain gh squash PRs; no VERSION file; flaky oracle suite). Per
ship.md tier-2: review verdict from a dispatched Sonnet review subagent
(items/009-review.md); `/code-review` as the independent second pass
(items/009-pr-review.md). Both gate the merge.

## Doc-sync done in ship
- CHANGELOG.md `[Unreleased]` gained an "F-domain repo adapter (item 009)" subsection.

## Notable pre-ship event
An integrity leak was caught + fixed BEFORE this PR opened (commits da37f94/cb86914):
the candidate prompt had named the golden-new helper + solution mechanics, and a
tracked test hardcoded the verbatim golden answer. Remediated to evaluator-only;
`git grep` confirms 0 golden tokens in tracked files. So this PR's diff is leak-free.
