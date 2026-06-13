PR: https://github.com/snowshine0216/agent-eval-lab/pull/18
Mode: A
Branch: feat/agentic-v1-008-runner-harden
Base: main
Title: feat(agentic-v1): harden D-runner + Qwen/SiliconFlow provider ladder (008)

## Ship path
Tier-2 (orchestrator-driven `gh pr create`), not `/ship`. Documented rationale:
- The repo's established convention is plain `gh` squash PRs (#14–#17), not `/ship`.
- No VERSION file exists, so `/ship`'s SemVer bump step has no target.
- An untracked `items/010-b-domain-artifacts.md` is in the working tree; `/ship`'s
  staging could sweep it into the 008 PR. Tier-2 pushes only committed branch
  state, structurally preventing the leak (public-repo integrity).
- The suite has known-flaky oracle-subprocess timeouts that could abort `/ship`
  non-deterministically.
Per ship.md tier-2 contract: the review verdict is produced by a dispatched
Sonnet review subagent (items/008-review.md), and `/code-review` runs as the
independent second pass (items/008-pr-review.md). Both still gate the merge.

## Doc-sync done in ship
- CHANGELOG.md `[Unreleased]` gained an "agentic_v1 runner hardening (item 008)" subsection.

## Branch commits (vs main)
- 7f3de5e docs(agentic-v1): open domains+runs continuation run (scaffold)
- 3ebd7d0 feat(agentic-v1): harden D-runner — bounded tool-history, provider-error→recorded, incremental JSONL+void sidecar, local Qwen3-8B + siliconflow ladder
- 1205fed docs(agentic-v1): 008 impl green + committed; subagent-driven for remaining work
- c1eda30 drift(008): PASS
- (CHANGELOG) docs(changelog): 008 runner hardening + siliconflow provider ladder
- (this) ship artifact
