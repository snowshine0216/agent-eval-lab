# claude-p F baseline — design

**Date** 2026-06-16 · **Branch** `feat/claude-p-f-baseline` · **Status** design (pre-implementation)

## Goal

Measure how vanilla Claude Code (Sonnet 4.6, no skills) performs on the F-set
repair tasks (F1/F2/F3) as a **baseline** — running the actual `claude -p` CLI as
the agent, rather than driving a model through the lab's own OpenAI-compatible
chat loop. This answers the owner's question "how does plain Claude do on these
tasks?" and gives a reference point alongside the F-ablation v2 roster
(deepseek / minimax / qwen).

### Non-goal / explicit scope boundary

This is **NOT** a fourth row in the v2 2×2 ablation table. `claude -p` is a
different harness: its own agent loop, its own native tools, its own scaffolding.
The 2×2 Factors (**P** = prompt nudges, **V** = `run_tests` feedback) do not map
onto it. Results live in a **separate report** and must never be presented as a
v2 arm. The frozen `experiments/f_ablation_spec.py` methodology and its
`spec_hash` are **not touched**.

## What "baseline" means here — two tool surfaces

Both surfaces run the same Sonnet 4.6 model on the same F tasks; they differ
**only** in the tools Claude is allowed:

| surface | tools allowed | tools denied | analogue |
|---|---|---|---|
| `edit-only` | Read, Edit, Write, Glob, Grep | Bash, WebFetch, WebSearch, task/agent tools | v2 **bare** arm (read+edit, cannot run tests) |
| `natural` | the above **+ Bash** | WebFetch, WebSearch, task/agent tools | Claude Code's real agentic mode (can run tests itself) |

The system prompt is identical across surfaces except one line: `edit-only`
keeps "Do not attempt to run tests"; `natural` drops it. **No Factor-P block** is
ever added, so the two baselines differ in exactly one variable (tools). This
lets us read the gap between "edit from reading alone" and "edit with a shell."

Full scale: **2 surfaces × 3 bases (F1/F2/F3) × k=5 = 30 attempts.**
First step (agreed): **smoke = 1 attempt** (F1, `edit-only`) to validate plumbing
and observe real cost, then **pause** for go-ahead before the full 30.

## Isolation — what makes it a *baseline*

The subprocess must be vanilla Claude Code, not "Claude + the owner's setup":

- `--disable-slash-commands` — disables all skills.
- **Clean `HOME`** (a temp dir) for the subprocess env, so `~/.claude` memory,
  installed skills/plugins, and the global `CLAUDE.md` do **not** load. The
  agent's only context is the F task prompt + the seeded repo tree.
- Run **inside the materialized temp working dir** (not this repo), so no project
  `CLAUDE.md` is inherited.
- **Bounding the run**: Claude Code 2.1.177 has **no `--max-turns` flag**, so the
  v2 40-round cap has no exact CLI analogue. We bound each attempt two ways: a
  **wall-clock subprocess timeout** (default 300s, primary) and
  **`--max-budget-usd`** (a per-attempt dollar safety cap). We record the actual
  `num_turns` from the result and report it, but do **not** hard-cap rounds — an
  honest, stated departure from v2's 40-round cap.
- No MCP servers configured for the subprocess.

Model id: **`claude-sonnet-4-6`** (the owner's "sonnet6"; there is no "Sonnet 6").

### Billing / cost model (decided)

The subprocess inherits the session's `ANTHROPIC_BASE_URL` + **OAuth
(subscription, Pro/Max)** auth — there is no `ANTHROPIC_API_KEY`. Consequences,
which differ fundamentally from the v2 roster's pay-per-token API keys:

- A `claude -p` run incurs **no separate per-token dollar charge**; it consumes
  the owner's **Claude usage quota / rate limits**. A 30-attempt agentic run
  (esp. `natural` mode) can eat a meaningful chunk of quota — hence smoke-first.
- `total_cost_usd` from `--output-format json` is the **API-equivalent computed
  cost**, recorded per attempt as an **efficiency metric** (comparable to the v2
  models' real spend), **not** an actual charge.
- `--max-budget-usd` is therefore a weak/secondary lever (a computed-cost stop
  that may be a no-op under OAuth); the **300s wall-clock timeout + attempt
  count** are the real safeguards. The report states Claude's cost column is
  quota-metered (API-equivalent), not billed dollars.

## Architecture

Grading in this codebase is a pure function of the **produced tree**:
`precompute_node_verdicts` reads `trajectory.final_state["files"]`
(`runners/node_oracle_edge.py:62`) and the held-out Node oracle overlays its
golden test and runs Node over that tree. And `run_f_candidate`
(`runners/f_candidate.py`) already takes an **injected `run_fn`**
`(edit_task, run_index) -> Trajectory`.

So the integration is: provide a claude-p `run_fn` with the **same signature** as
`make_f_run_fn`, and plug it into the existing per-task k-loop, env-invalid
masking, VOID logic (`ReplacementOutcome`), grader (`grade_f_attempt`), and
efficiency rollup — all unchanged.

Rejected alternatives:
- **Graft claude-p in as extra "arms" of `run-f-ablation`** — pollutes the frozen
  2×2 spec_hash and conflates incomparable harnesses. Rejected.
- **Standalone script calling the oracle directly** — reimplements the k-loop /
  VOID / efficiency rollup and diverges from house records. Rejected.

## Components

### `runners/claude_cli_candidate.py` (new)

Split pure / edge per house style.

**Pure**
- `claude_system_prompt(surface) -> str` — the F edit instructions; reuses the
  `_EDIT_SYSTEM` intent from `f_candidate.py`, dropping the "do not run tests"
  sentence for `natural`. No Factor-P block.
- `build_claude_argv(*, model, surface, prompt, max_budget_usd) -> list[str]`
  — assembles `claude -p … --model <model> --output-format json
  --disable-slash-commands --max-budget-usd <amount>` plus per-surface
  `--allowedTools …` / `--disallowedTools …`. Pure list construction. (No
  `--max-turns` — not a flag in 2.1.177; rounds are bounded by the subprocess
  timeout instead.)
- `parse_claude_result(stdout) -> ClaudeRunMeta` — parse the `--output-format json`
  single-result object: `usage.input_tokens` → `prompt_tokens`,
  `usage.output_tokens` → `completion_tokens`, plus `num_turns`,
  `total_cost_usd`, `is_error`. Frozen dataclass. Raises a typed parse error on
  malformed JSON (caller maps to env-invalid).

**Edge**
- `materialize_tree(tree: Mapping[str, str], dest: Path) -> None` — write the
  `{posix-relpath: content}` seeded tree to disk under `dest`.
- `read_back_tree(dest: Path, *, ignore=(".git", "node_modules")) -> dict[str, str]`
  — read the produced files back into the `{relpath: content}` shape the oracle
  expects.
- `make_claude_run_fn(*, model, surface, run_subprocess, workdir_factory) -> run_fn`
  — the injected-dependency orchestrator. Per attempt: create temp workdir +
  temp HOME via `workdir_factory` → `materialize_tree(edit_task.initial_state["files"], workdir)`
  → `run_subprocess(build_claude_argv(...))` → `parse_claude_result(stdout)` →
  `read_back_tree(workdir)` → build a synthetic
  `Trajectory(final_state={"files": produced}, usage=Usage(prompt_tokens, completion_tokens),
  rounds=num_turns, max_rounds=40, ...)`. `run_subprocess` and `workdir_factory`
  are injected so unit tests need no real `claude` and no network.

### CLI subcommand `run-f-claude-baseline` (in `cli.py`)

- `--surface {edit-only,natural,both}` (default `both`)
- `--k 5`
- `--bases f1 f2 f3` (default all three)
- `--model claude-sonnet-4-6`
- `--smoke` — overrides to 1 base (f1), 1 attempt, `edit-only`; for the first run
- `--out <dir>` (default `reports/agentic-v1/f-claude-baseline/`)

Drives `run_f_candidate` once per surface, writing per-attempt records (the
existing record format) plus a summary.

### Report

New dir `reports/agentic-v1/f-claude-baseline/`. Summary table: pass^k and pass@1
per (surface × base), median rounds, median output tokens, total `total_cost_usd`
per surface. A header line states explicitly that these are **Claude Code
baselines, not v2 ablation arms.**

## Error handling

A claude-p subprocess failure — non-zero exit, `is_error: true`, timeout, or
unparseable JSON — is an **env-invalidity**, not a model failure (parity with a
provider HTTP rejection). The attempt is masked from `valid_runs`, flagged
invalid in `attempts`, and a base that lands `< k` clean attempts is **VOID**
(never scored over `<k`, D34). This reuses the existing `is_env_invalid_run`
path: the synthetic trajectory/grade for a failed subprocess carries the
env-invalid marker the grader already recognises. A produced tree identical to
the seeded tree (Claude made no edit) is a **legitimate FAIL**, not env-invalid.

## Testing (TDD)

Unit (no subprocess, no network):
- `build_claude_argv` — correct flags per surface; skills disabled; max-turns set;
  Bash present iff `natural`.
- `parse_claude_result` — happy path + malformed JSON + `is_error: true`.
- `claude_system_prompt` — `natural` drops the no-tests line; neither carries a
  Factor-P block; both otherwise identical.
- `read_back_tree` — round-trips a materialized tree; ignores `.git`/`node_modules`.
- `make_claude_run_fn` — with a fake `run_subprocess` returning canned JSON and a
  fake `workdir_factory`: asserts the produced Trajectory's `final_state["files"]`,
  `usage`, `rounds`; asserts subprocess-failure → env-invalid trajectory.

Integration: the **smoke run** against the real `claude` CLI is the end-to-end
check (materialize → run → parse → read back → oracle grade → record + cost).

Grading itself is the existing, already-tested oracle path — unchanged.

## Open questions (resolved by defaults unless owner objects)

- Timeout per attempt: default **300s** wall per claude-p attempt (the primary
  round-bound, since there's no `--max-turns`); a longer fix loop on `natural` is
  plausible — revisit if smoke hits it. `--max-budget-usd` default: **0.50**/attempt.
- `natural`'s Bash can run the **in-tree** F3 guard tests, but never the held-out
  golden grading test (D19 — never seeded). This is accepted and noted in the
  report as the defining difference of the `natural` surface.
