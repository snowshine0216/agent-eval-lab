# Agent Eval Lab

A reproducible agent-evaluation harness: tasks carry a tagged-union
`VerificationSpec`; an effectful runner produces a `Trajectory`; pure tiered
graders interpret the spec into a `GradeResult`; pure metrics aggregate runs
into reliability and cost numbers. Functional core, imperative shell.

## Language

### Verification & grading

**VerificationSpec**:
The tagged union describing how a task is graded. Each variant
(`OutputMatchSpec`, `ToolCallMatchSpec`, `FinalStateSpec`, `TrajectorySpec`,
`AllOf`, `LlmJudgeSpec`, and `ExecutionSpec`) carries only the fields that
variant needs, so illegal states are unrepresentable. It is inert serializable
data — behavior lives in the pure graders, never on the record.
_Avoid_: "grader config", "scorer spec", "rubric" (the rubric is a judge
artifact, distinct).

**Constraint**:
A serializable data variant *inside* a `FinalStateSpec` or `TrajectorySpec` that
a pure interpreter evaluates. State constraints (`StateEquals`, `StateContains`)
assert outcome; trajectory constraints (`NoToolCall`, `OnlyModifies`,
`MaxToolCalls`) assert policy. A constraint is not itself a `VerificationSpec`.
_Avoid_: "rule", "check", "assertion" (these blur constraint vs spec vs grader).

**Outcome verification**:
Grading the *world-state a run reached*, independent of which tool path reached
it (`FinalStateSpec`). Many valid paths can pass the same final-state check.
_Avoid_: "result check", "state assertion" (informal).

**Policy verification**:
Grading the *path a run took* for forbidden side-effects, even when the outcome
is correct (`TrajectorySpec`). The complement of outcome verification: outcome
says "did it get there", policy says "did it harm nothing on the way".
_Avoid_: "side-effect check", "trajectory grading" (overloaded — `TrajectorySpec`
grades policy, not the whole trajectory's correctness).

**Path-independence**:
The property that `FinalStateSpec` grades the reached world-state, not the
sequence of tool calls — so two runs taking different valid tool paths to the
same `final_state` grade identically. Path-independence is *outcome only*;
policy is reintroduced deliberately via `TrajectorySpec` so path-independence
never means "ignore harmful actions".
_Avoid_: "order-independent" (that's the `multiset` match mode of
`ToolCallMatchSpec`, a different concept).

**final_state**:
The post-loop world-state snapshot the runner records on the `Trajectory`. It is
the single artifact the state/policy graders read; they never replay the world
to recompute it. `None` when no state-graded run produced one. Distinct from
`Task.initial_state` (the pre-run world the runner seeds and the diff baseline).
_Avoid_: "world", "final world" (ambiguous with the runner's live `state` local).

**FailureCategory**:
The closed literal taxonomy a `GradeResult` carries to explain *why* a run
failed (`malformed_call`, `schema_violation`, `wrong_tool`, …,
`forbidden_action`, `step_limit_exceeded`). `forbidden_action` and
`step_limit_exceeded` name *policy* breaches only. An outcome assertion that
simply does not match (a `StateEquals`/`StateContains`/`OutputMatchSpec` miss)
carries `failure_reason=None` — it is a missed expectation, not a forbidden
action.
The task/agent/harness axis is *not* here — that is **RunClassification**, a
derived report-time interpretation, never a grade field.
_Avoid_: adding a category for plain assertion misses; `None` is the category
for "the answer was wrong, no policy was violated".

**forbidden_action**:
The `FailureCategory` for a *policy* breach where a run did something it must not:
a `NoToolCall`-named tool was called, or a state path outside the `OnlyModifies`
allowlist changed. Not used for a value simply being wrong.

**step_limit_exceeded**:
The `FailureCategory` for a `MaxToolCalls(n)` breach: the total number of tool
calls across the trajectory exceeded `n`. Counts *calls* (each entry of every
`ToolCallTurn.tool_calls`), not turns.

**AllOf**:
The composite `VerificationSpec` variant: a conjunction of nested specs, all of
which must pass. It evaluates *every* sub-spec (no short-circuit) so the audit
trail is complete, ANDs their `passed`, and reports the `failure_reason` of the
*first* failing sub-spec in declared order. Recursive: an `AllOf` may nest
another `AllOf`.
_Avoid_: "compound spec", "and-spec".

### Existing terms (for reference, defined by the locked design)

**Task**:
A single evaluation unit: id, capability, input (messages + available tool
schemas), a `VerificationSpec`, metadata, and an optional `initial_state`.

**Trajectory**:
The record a single run emits: the turns, token usage, latency, `run_index`,
stop reason, and (when state-graded) `final_state`. Immutable; replayable from
`initial_state`.

**GradeResult**:
The pure grader's verdict over one trajectory: `grader_id`, `passed`, `score`,
`evidence` (the audit trail of what the grader saw), and `failure_reason`.

### Dataset engineering

**Distractor tool**:
A registered, schema-valid tool whose name/behavior deliberately overlaps a
correct tool so that picking it is a *gradeable wrong path*, never a correct one
(`archive_ticket` vs `update_ticket`, `find_account` vs `get_account`,
`draft_email` vs `send_email`). A distractor never appears in any task's
`ExpectedToolCall`, and its signature state (`status:"archived"`,
`emails.*.state:"draft"`) is never asserted as a *passing* outcome — only forbidden
(`NoToolCall`) or used as the wrong-path state a correct `FinalStateSpec`
distinguishes against. The conformance test enforces "distractor never expected".
_Avoid_: "filler tool", "decoy" (a distractor must be gradeable, not noise).

**Difficulty knob**:
A named lever from a closed *per-world dialect* that a task records in
`metadata.difficulty_knob` to declare *the one thing* that makes it hard.
Workspace dialect: `multi_step_depth`, `derived_argument`, `distractor_count`,
`argument_complexity`, `layered_constraint`. Code dialect (code_repair_v1):
`fault_distance`, `multi_hunk`, `oracle_breadth`, `spec_obliqueness`,
`constraint_budget`, `distractor_file`. A knob name is never reused across
dialects with a mutated meaning. Long-horizon is a *property* (chain depth via
`multi_step_depth` + `max_steps`), not a knob of its own.
_Avoid_: "hardness", "difficulty level" (the *tier* is the level; the knob is the
mechanism).

**Tier**:
The coarse hardness band of a task (`T1` sanity, `T2` moderate, `T3` hard, `T4`
adversarial), carrying a per-tier *expected-failure rationale*. Orthogonal to
`capability` (the skill isolated) and to `difficulty_knob` (the mechanism). The
hard tiers (T3+T4) are the majority of v2 by directive.
_Avoid_: "level", "grade" (grade is the run verdict, `GradeResult`).

**State-dependent chain**:
A multi-call task where at least one call's arguments are *unknowable* from the
prompt or `initial_state` alone — they derive from a prior call's *result* (a
minted id, or an id/field only surfaced by `list_tickets`/`find_account`). The
discriminating opposite of a *rote chain* (independent calls whose args are all
present up front). The conformance test enforces a structural proxy: a
`multi_step_depth`/`derived_argument` task must reference at least one entity not
present in `initial_state` or the prompt.
_Avoid_: "long chain", "multi-step" (length alone does not imply dependence).

**provenance**:
Closed `metadata.provenance` vocabulary recording how a task was produced;
counted in the dataset card (§9). `hand_written` is canonical for human-authored
tasks (established by v1; v2 reuses it). A future generator adds one new value
(`generated`), not a synonym.
_Avoid_: "hand_authored", "hand-authored", "manual" (synonyms fracture the count).

**version (dataset)**:
The `metadata.version` string naming the *dataset/world generation* a task belongs
to (`"1"` for v1, `"2"` for v2). Co-varies with the dataset's `world_template_id`
family (`workspace-v1`/`workspace-v2`, `code-v1-*`). The counter is scoped to its
dataset lineage — `workspace_tool_use` and `code_repair` count independently, so
`code_repair_v1` is not "older" than `workspace_tool_use_v2`. It is the
world-revision counter, NOT a per-row append-only revision number.
_Avoid_: "schema version", "row version" (it versions the world+task-set, not the
record schema).

**world_template_id**:
The `metadata.world_template_id` naming the parametrized world a task is built on
(`workspace-v1`, `workspace-v2`, `code-v1-<program-slug>`). It is the §7
*isolation boundary* for the Weeks 9-10 train/dev/held-out splits — a template
(and its seed family) belongs to exactly one partition. Granularity is a
per-dataset declaration: workspace datasets share one template per generation;
code_repair_v1 declares one template per task (one program family each) so split
partitioning never has to treat the dataset as a single block. Carried on every
task from day one so splits never need retrofitting.
_Avoid_: "world id", "scenario id" (it names the *template*, not an instance).

**max_steps (task hint)**:
The optional `metadata.max_steps` a task declares as the loop-iteration budget its
intended dependent chain needs, floored at `dependent_calls + 2` (headroom for the
model's read/confirm turns). It is *data*; threading it through the runner is item
004's contract. Distinct from the runner's run-level `max_steps` argument (today a
global CLI default of 6).
_Avoid_: "step limit", "max turns" (`step_limit_exceeded` is the policy
`FailureCategory`; `max_steps` here is the per-task budget hint).

**condition_id**:
The `provider:model` identity (`runners/config.condition_id`) stamped on every
`RunResult` and used to name its run artifact (`runs-<slug>.jsonl`). It identifies
the *model under test*, NOT the agent configuration — two runs of the same model
under different system prompts share one `condition_id` (resolved by the
**prompt-config tag**). The join key from a run record back to its condition.
_Avoid_: "run id" (that is `run_index` within a condition), "model name" (it pairs
provider *and* model, so two providers serving the same model never collide).

**prompt-config tag**:
The optional suffix appended to a run artifact's slug
(`runs-<condition-slug>__<tag>.jsonl`, e.g. `…__planning.jsonl`) that distinguishes
two agent configurations sharing one **condition_id** — the same model under
`default` vs `planning` system prompts (item 004's two-config comparison). Empty
when no `--system-prompt-file` is given, so the v1 artifact filename is unchanged.
The *source path*, not the in-record `condition_id`, is what tells the two configs
apart (ADR-0007).
_Avoid_: "config id", "variant id" (the tag rides the *filename*, not the frozen
`RunResult` schema, which keeps `condition_id = provider:model`).

**review (task)**:
The `metadata.review` field (`"passed:<rubric-version>"`) that rides each
append-only row as its *machine-checkable, frozen* proof the task passed the
authoring rubric. The `review-ledger.md` is the *human-readable, regenerable* audit
view keyed by task id; the field, not the ledger, is the source of truth for review
coverage.
_Avoid_: "rubric" alone (the *rubric* is the author's task-validity checklist —
distinct from the item-003 judge rubric, a known naming hazard).

**sidecar (dataset)**:
A dataset-adjacent JSON keyed by task id (`*_tiers.json`,
`*_review_fixtures.json`) carrying data the harness never loads — tiers for the
report tooling; bug classes and solution/hack/distractor fixtures for conformance
and review. Sidecars freeze with their dataset version (the append-only convention
covers them), and a fixtures sidecar joins the Weeks 9-10 never-train manifest
because it carries solutions.
_Avoid_: "metadata file" (`TaskMetadata` is the in-row contract; sidecars are
deliberately outside it), "fixture dataset" (sidecars are not task sets).

**visible tests**:
The test files present in the agent-visible file tree — basename matching
`test_*.py`; `*_test.py` basenames are banned so the naming convention equals
pytest collection. Collected mid-trajectory by `run_tests` and again at the oracle
run via the combined tree; they prove nothing about the **oracle tests**, whose
paths are disjoint by policy (ADR-0012). A *prose-only* task has none — its
initial-tree suite status is `no_tests`.
_Avoid_: "public tests", "agent tests" (the agent may also *write* tests; visible
names tree membership, not authorship).

**distractor file**:
code-world's analog of the **distractor tool**: a correct file in the initial tree
that plausibly looks at fault. The reference solution leaves it byte-identical and
an oracle regression test references it, so modifying the red herring is a
*gradeable* wrong path, never noise.
_Avoid_: "decoy file", "filler file" (a distractor must be gradeable).

**bug class**:
The closed per-dataset vocabulary naming the planted defect's species
(code_repair_v1: `off_by_one`, `logic_inversion`, `exception_handling`,
`type_coercion`, `boundary_condition`, `aliasing_mutation`), recorded in the
review-fixtures sidecar and the ledger — never on `TaskMetadata`. Orthogonal to
capability (evidence source), knob (hardness mechanism), and tier (band).
_Avoid_: "bug type"; "defect category" (collides with `FailureCategory`).

**hack fixture**:
The minimal patch that satisfies a task's **visible tests** by special-casing
their inputs while leaving the program unrepaired. Conformance/review input only
(it rides the review-fixtures sidecar): it must pass the visible suite and fail
the oracle, proving oracle breadth mechanically exactly where the taxonomy claims
overfit resistance (ADR-0012).
_Avoid_: "cheat solution" (it is an authored fixture, not an agent behavior).

**reference solution**:
The per-task solution files in the review-fixtures sidecar whose overlay onto the
initial tree passes both the visible suite and the oracle inside the sandbox
budget — the mechanical solvability witness. Never rendered into any prompt;
agents are never compared to it line-by-line.
_Avoid_: "golden patch", "answer key" (it witnesses solvability, not the unique
fix).

### Model-based grading & calibration

**Judge rubric**:
The anchored 1-5 scoring guide a `LlmJudgeSpec` carries (`spec.rubric`) telling a
model how to score one *irreducibly subjective* quality. This is the *third*
distinct sense of "rubric" in the project, and the only one CONTEXT.md endorses
unqualified-as "judge rubric": the **authoring rubric** (a task author's
task-validity checklist, recorded in `metadata.review`) and the
**`VerificationSpec`** (the tagged-union grading config) are both separate things.
_Avoid_: "scoring config", "grader config" (those name the `VerificationSpec`);
bare "rubric" (always qualify: *judge* rubric vs *authoring* rubric).

**Summary fidelity**:
The first judged quality: does the final assistant message *truthfully and
completely* reflect the tool actions actually taken in the trajectory, without
claiming actions that did not happen? It is the irreducible subjective residue
*after* `FinalStateSpec` (outcome) and `TrajectorySpec` (policy) have graded what
a deterministic check can reach. A judge non-pass here is a *missed expectation*
(`failure_reason=None`), never a policy breach.
_Avoid_: "helpfulness", "clarity" (too subjective to anchor); "correctness"
(that is the deterministic legs' job).

**JudgeVerdict**:
The serializable record an edge `run_judge` produces and threads into the pure
grader: `score` (the 1-5 integer), `rationale`, `raw` (the model reply verbatim),
`judge_model`, and `prompt_hash`. It is the *only* channel from the I/O edge to
the pure grader, so it is self-describing — the pure grader copies its fields into
`GradeResult.evidence` and never learns `judge_model`/`prompt_hash` any other way.
A failed judge call yields a `JudgeError` (edge) or `JudgeParseFailure` (pure)
instead — never a coerced score — exactly as the runtime emits `ToolFailure`
rather than a faked result.
_Avoid_: "judge result" (collides with `GradeResult`), "score" alone (the verdict
carries more than the score).

**prompt hash**:
The `sha256` over the canonical-JSON rendering of a judge prompt — a pure function
of `(LlmJudgeSpec, Trajectory)`. It keys the verdict map the edge pre-computes and
the pure grader reads. Because every interpretation-affecting field (notably
`scale`) is *rendered into the prompt*, two judge legs sharing a hash provably
share a verdict (correct dedup), and two legs that should differ render different
prompts and hash apart.
_Avoid_: "cache key" (it *would* key a cache, but no cache ships in item 003;
recording it for auditability is the point).

**Annotation packet**:
The blind, rubric-anchored, fixed-item-order JSONL artifact an annotator (human or
LLM) scores against. It shows *only* the trajectory (final message + tool-call/
result digest) with an empty score field and carries a `packet_format` version and
a `rubric_version`-it **never** contains any judge score (blind labeling, §6.5
step 1). The intended-label of each fixture lives in the *fixture design table*,
outside the packet.
_Avoid_: "label file" (a *filled* packet is the label file), "dataset" (the packet
is derived from the calibration corpus, not a task set).

**Cohen's κ (headline, binary)**:
The project's headline judge-reliability statistic: Cohen's κ computed on the
*binarized* label (`score >= 4` -> "faithful"), with a seeded percentile bootstrap
CI resampling *items*. Binary because κ then measures the pass/fail decision the
grader actually ships (`GradeResult.passed`). Quadratic-**weighted κ** over the raw
1-5 scale is reported *secondary/descriptive* (near-miss vs gross disagreement),
never as the headline.
_Avoid_: "agreement" alone (observed agreement is a *separate* reported number);
"accuracy" (κ is chance-corrected).

**Provisional calibration**:
An LLM-LLM agreement run (two registry models as annotators, e.g. `deepseek` +
`glm`) over the calibration corpus that proves the packet -> κ pipeline end-to-end.
It is **not** the human-human reliability §6.5 step 2 requires; every artifact it
produces is loudly labeled PROVISIONAL and protocol steps 2-3 stay OPEN until a
human fills the packet.
_Avoid_: "calibration" unqualified (the real calibration is human-human first);
treating LLM-LLM κ as a reliability verdict.

### Code-world & execution

**code-world**:
The second world (after workspace-world): its state is a **file tree** and its
tools are `read_file`, `write_file`, `list_files`, `run_tests`. Same pure
`apply` contract as workspace-world; only `run_tests` reaches the **execution
edge**, via an **effect-request**.
_Avoid_: "code workspace" (collides with workspace-world), "repo world",
"sandbox world" (the sandbox is the edge's temp dir, not the world).

**file tree**:
Code-world's state shape: a flat immutable mapping of POSIX-relative path →
text content. Every reachable tree is materializable by construction — path
canonical-form and file/directory-collision rules are enforced by the pure
tools, so no valid state can fail to land on disk.
_Avoid_: "filesystem" (that's the materialized temp dir at the edge), "repo",
"workspace" (taken).

**effect-request**:
The bridge for a tool whose result requires I/O: pure `apply` returns a
serializable request describing *what* to execute (in the outcome position,
instead of a `ToolOutcome`); the runner loop — matching on the request *type*,
never the tool name — fulfills it at the edge and records the fulfilled result
on the trajectory as ordinary data. The mid-trajectory generalization of
ADR-0005's precompute rule (ADR-0008). Replay never re-fulfills: a recorded
result is data, like a recorded model reply.
_Avoid_: "thunk", "deferred effect", "callback" (mechanics, not the contract);
"tool interception" (the rejected name-based alternative).

**ExecutionRequest**:
The code-world effect-request: a frozen, serializable snapshot of the file tree
to run tests over. It carries *only* the tree — timeout and interpreter are
edge policy — so the request stays a pure function of state and the agent
controls neither.
_Avoid_: "test request", "exec command".

**ExecutionResult**:
The structured, deterministic record of one sandboxed pytest run: suite
**status (execution)**, exit code, counts (passed/failed/errors/skipped),
per-test statuses sorted by test id, and head-truncated **canonicalized
output**. Wall-clock duration is deliberately absent — it is the one
nondeterministic observable.
_Avoid_: "run result" (that is `RunResult`, the task×condition×grade record),
"test result" (a per-test entry, not the suite record).

**status (execution)**:
The closed suite-level literal on an `ExecutionResult`:
`passed | failed | error | timeout | no_tests` (per-test entries use
`passed | failed | error | skipped`).
_Avoid_: "outcome" (already two senses: `ToolOutcome` and *outcome
verification*).

**execution edge**:
The single place subprocess/filesystem I/O happens for code-world: materialize
the file tree into a fresh temp dir, run pinned-interpreter pytest in a
scrubbed from-scratch environment under a hard timeout, parse the JUnit XML,
canonicalize the output, clean up in a `finally`. Distinct from the **oracle
edge**, the grading-side precompute boundary that calls it.
_Avoid_: "sandbox runner", "test harness" (overloaded).

**sandbox**:
The throwaway execution environment the edge builds per run: fresh temp dir +
from-scratch env (no inherited secrets or proxy vars) + process-group kill on
timeout. Isolation is temp-dir-and-convention level, not kernel level — a
documented limitation; no containers.
_Avoid_: "container", "jail" (over-claim kernel isolation).

**canonicalized output**:
The recorded form of a sandbox run's stdout/stderr: the random temp-dir root
replaced by the fixed `<sandbox>` placeholder and the pytest timing token
normalized, then head-truncated at a fixed byte cap with an explicit marker.
Reproducibility (byte-identical `ExecutionResult`) is claimed over this form,
never over verbatim output (ADR-0009).
_Avoid_: "raw output" (verbatim is precisely what is never recorded);
"scrubbed output" (the *env* is scrubbed; the *record* is canonicalized).

**oracle tests**:
The held-out test files an `ExecutionSpec` carries (`held_out_tests`:
POSIX-relative path → content): a file-tree fragment the agent never sees,
overlaid onto the trajectory's final tree and run at the **oracle edge** as
the Tier-2 verdict source. Distinct from the **visible tests** the agent runs
mid-trajectory via `run_tests`, which prove nothing about the oracle; in
code-repair datasets oracle paths are disjoint from every initial-tree path,
with breadth proven mechanically rather than by superset (ADR-0012).
_Avoid_: "hidden tests" (vague), "test suite" unqualified; reusing mid-run
`run_tests` results as the oracle (they cover only what the agent saw).

**overlay (oracle-wins)**:
The pure combination of **oracle tests** onto a final **file tree** before the
grading run: on an exact-path collision the oracle file wins and the agent's
path is recorded as a **displaced path**; a canonical-prefix collision
(identical NFC+casefold form, different spelling) is a structured
`tree_collision` error — a graded record, never a crash (ADR-0010).
_Avoid_: "merge" (no content merging happens), "agent-wins" (a reward-hack
vector).

**displaced path**:
An agent-written path the oracle replaced during the **overlay**. Displacement
is evidence on the `ExecutionVerdict`, never an automatic fail — the oracle's
verdict stays the verdict.
_Avoid_: "shadowed" (suggests the file is merely hidden), "overwritten"
(suggests mutation; the overlay is pure).

**execution hash**:
The sha256 over the canonical-JSON rendering of an `ExecutionSpec`'s oracle
tests and raw timeout plus the final file tree — a pure function of
`(spec, final_tree)` computable on both sides of the boundary and well-defined
even when the overlay would collide. It keys the `ExecutionVerdict` in the
shared verdict map: the execution analogue of the judge's **prompt hash**
(ADR-0011).
_Avoid_: "tree hash" (it is not a hash of the combined tree), "cache key" (no
cache ships; auditability and dedup-by-construction are the point).

**ExecutionVerdict**:
The serializable record the **oracle edge** precomputes per reachable
`ExecutionSpec` — the oracle run's `ExecutionResult` plus its **execution
hash** and **displaced paths** — threaded into the pure `grade_execution`,
which only reads it. A failed precompute yields a serializable
`ExecutionError` (`tree_collision` | `harness`) at the same key instead —
never an exception in the map, mirroring `JudgeVerdict`/`JudgeError`.
_Avoid_: "execution result" (that is `ExecutionResult`, the suite record it
wraps); "verdict" alone (which one?).

**oracle edge**:
The grading-side precompute boundary (`runners/oracle_edge.py`): collect the
reachable `ExecutionSpec`s, **overlay** each onto the final tree (pure), run
the **execution edge**'s sandboxed pytest, and emit a verdict map keyed by
**execution hash** — post-trajectory, because the final tree is only knowable
then. The execution analogue of the judge edge.
_Avoid_: "execution edge" (taken — that is `pytest_edge`'s sandbox boundary),
"grading edge" unqualified.

### Failure classification & final report

**RunClassification (failure classification)**:
The derived, versioned (`fc-v1`) interpretation layer mapping every graded
`RunResult` to exactly one of `passed | task_failure | agent_failure |
harness_failure` plus one closed subcategory, computed at report time from the
mechanical discriminators already on the record (suite **status (execution)**,
execution-error kind, stop reason, parse failure, `failure_reason`). Derived,
never stored: it is an interpretation *over* grades, not a grade —
`GradeResult` and `FailureCategory` are untouched, and a classifier-version
bump is a pure re-render of committed runs, never a re-run.
_Avoid_: "failure taxonomy" (that is `FailureCategory`, the grade-level
vocabulary); "error class"; storing the classification on `RunResult`.

**world binding**:
The frozen `(registry, apply_fn, executor)` triple a pure resolver derives from
a task's `available_tools` by tool-name membership — the dataset row is the
single source of world truth (workspace-world vs code-world). Tool-name spaces
are disjoint across worlds by tested invariant; an unknown name, a cross-world
mix, or an empty tool list refuses to resolve (fail loud, never a silent
default).
_Avoid_: "world config", "world flag" (the rejected CLI-flag alternative);
"environment" (overloaded).

**task-defect candidate**:
A task id that every non-blocked condition with records for it unanimously
fails (all recorded runs), flagged by the final report for *human review* —
never auto-classified as `task_failure`. Conformance already proves
solvability, oracle breadth, and symptom reality, so unanimity defaults to
"hard, not defective" pending adjudication. The only *mechanical*
post-conformance task-defect signal is an empty oracle at grading time
(suite status `no_tests`).
_Avoid_: "broken task" (presumes the adjudication); "task failure" unqualified
(that is the classifier category, which the queue deliberately does not
assign).

## Example dialogue

> **Dev:** The task says "close ticket T-1 and don't email anyone". Is that one
> spec or two?
>
> **Domain expert:** One composite. An `AllOf` of two specs. The
> `FinalStateSpec` is the *outcome* check — `StateEquals` on
> `tickets.T-1.status == "closed"`. The `TrajectorySpec` is the *policy* check —
> `NoToolCall("send_email")` plus maybe `OnlyModifies(("tickets.T-1",))`.
>
> **Dev:** If the agent closes the ticket by a weird three-tool path, does it
> still pass the outcome check?
>
> **Domain expert:** Yes — that's path-independence. `FinalStateSpec` reads the
> reached `final_state`, not the path. But if it sent an email along the way the
> *policy* check fails with `forbidden_action`, even though the outcome was
> right. Path-independence never means "ignore harm".
>
> **Dev:** And if the ticket just ended up `"open"` instead of `"closed"`?
>
> **Domain expert:** That's an outcome miss, not a policy breach — the
> `StateEquals` fails with `failure_reason=None`. We reserve `forbidden_action`
> and `step_limit_exceeded` for things the agent must not *do*.
>
> **Dev:** For v2 I wrote a T4 task that creates eight tickets in one go. Eight
> calls — that's a long horizon, right?
>
> **Domain expert:** Eight *independent* creates is a **rote chain**, not a
> **state-dependent chain**. Every title is in the prompt; nothing derives from a
> prior **result**. Length isn't the **difficulty knob** — `multi_step_depth`
> means step N's args are unknowable until step N-1 returns. The conformance test
> would reject it: a `multi_step_depth` task must reference an id that isn't in
> `initial_state` or the prompt, like the ticket `list_tickets` says is the oldest.
>
> **Dev:** It uses `draft_email` to notify the owner. The `FinalStateSpec` checks
> `emails.e-1.state == "draft"`. Pass?
>
> **Domain expert:** No — `draft_email` is a **distractor**. "Notify" means
> *send*. A correct task asserts `emails.e-1.state == "sent"` and the conformance
> check forbids a distractor's signature state (`"draft"`, `"archived"`) ever being
> a *passing* outcome. The distractor only shows up as the wrong path a correct
> spec discriminates against, or inside a `NoToolCall`.
>
> **Dev:** And the budget — `max_steps`?
>
> **Domain expert:** That's the per-task `metadata.max_steps`, floored at dependent
> calls + 2. It's *data*; the runner still takes a global default of 6 today, so
> item 004 must thread the per-task value or every T3/T4 task starves at the step
> limit. We ship the contract now and prove it with the conformance floor.
>
> **Dev:** The ticket closed, no email sent — but the agent's final message says
> "I closed T-1 and emailed the owner." `FinalStateSpec` passes. Is the run good?
>
> **Domain expert:** Outcome and policy pass, but **summary fidelity** fails — it
> claimed an email it never sent. No deterministic check reaches that; it's the
> Tier-3 residue. So we add a `LlmJudgeSpec` *inside* the `AllOf`, beside the
> deterministic legs — the judge scores the **judge rubric** 1-5, the edge returns
> a **JudgeVerdict** keyed by **prompt hash**, and the pure grader reads it. That
> fabrication is anchor 2, well below the `score >= 4` faithful cut.
>
> **Dev:** So the headline reliability number is the average 1-5 score?
>
> **Domain expert:** No-the headline is **binary Cohen's κ** on the `>=4`
> binarization, because κ measures the pass/fail decision we actually ship.
> Weighted κ over the raw 1-5 is a *secondary* near-miss-vs-gross diagnostic. And
> κ means nothing until it's calibrated: ≥2 humans label a blind **annotation
> packet** first, human-human κ before judge-human κ. We can't recruit humans in
> an autonomous run, so we ship a **provisional calibration** — `deepseek` vs
> `glm` as annotators — loudly labeled NOT the human reliability the protocol
> requires, just proof the pipeline runs.
>
> **Dev:** In code-world the agent calls `run_tests` and three tests fail.
> That's a `ToolFailure`, right?
>
> **Domain expert:** No — the tool did its job: it ran the tests and reported.
> A fulfilled **effect-request** always records a `ToolSuccess` carrying the
> serialized **ExecutionResult**; its **status** says `failed`. `ToolFailure`
> is reserved for the pure layer — a bad path, a schema violation. And don't
> call the suite status the "outcome" — that word is already taken twice.
>
> **Dev:** But `apply` is pure. Who actually runs pytest?
>
> **Domain expert:** The **execution edge**, and only when the loop fulfills
> the **ExecutionRequest** that pure `apply` returned. The request is just the
> **file tree** snapshot — timeout and interpreter are edge policy, not agent
> data. And replay never re-runs anything: the recorded result is data on the
> trajectory, exactly like a recorded model reply.
>
> **Dev:** The recorded stderr says `<sandbox>/test_foo.py` — that's not the
> real path. Bug?
>
> **Domain expert:** Deliberate — that's **canonicalized output**. The real
> temp dir is random per run, so verbatim output could never be byte-identical.
> We canonicalize so reproducibility is a property of the record, then truncate
> at the cap.
>
> **Dev:** Grading time: the agent wrote its own `tests/test_app.py`, and the
> task's **oracle tests** carry the same path. Who wins?
>
> **Domain expert:** The oracle — the **overlay** is oracle-wins, and
> `tests/test_app.py` is recorded as a **displaced path** in evidence. Anything
> else lets the agent pre-write a trivial suite at the oracle's path and grade
> itself. Displacement isn't a fail; the oracle's verdict stays the verdict.
> But if the agent wrote `Tests/test_app.py` — same canonical path, different
> spelling — that's a `tree_collision`: the **oracle edge** records a
> structured `ExecutionError`, the grader emits a non-pass, nothing crashes.
>
> **Dev:** And that verdict is keyed how — task id?
>
> **Domain expert:** By **execution hash** — sha256 of the oracle tests, the
> spec's raw timeout, and the final tree. Pure on both sides of the boundary,
> like the judge's **prompt hash**, and well-defined even when the overlay
> would collide. Same map, too: `ExecutionVerdict`s and `JudgeVerdict`s coexist
> in the one `verdicts` mapping, discriminated by type.
