# Run artifacts gain an optional prompt-config tag; the `RunResult` record schema stays frozen

The Weeks 3-4 two-configuration comparison (item 004) runs the *same* model
(`deepseek:deepseek-v4-pro`) under two system-prompt configurations (`default`
vs `planning`). But the run identity, `condition_id`, is `provider:model`
(`runners/config.condition_id`) and is stamped *inside* every `RunResult`
(`records/serialize.run_result_to_dict`). So both configurations would slug to
the **same** artifact (`runs-deepseek-deepseek-v4-pro.jsonl`) and carry an
**identical** in-record `condition_id` — the second run silently overwrites the
first. This is the *exact* cross-model-overwrite bug class the repo already fixed
once (commit c744b5f, CHANGELOG `Fixed`, guarded by
`test_artifacts_are_distinct_per_model_under_one_provider`).

We decided to **extend the artifact slug with an optional prompt-config tag**
(`runs-<condition-slug>__<tag>.jsonl`, e.g. `…__default.jsonl` / `…__planning.jsonl`),
derived from the `--system-prompt-file` fixture stem. When no system-prompt file
is given the tag is empty and the filename is **byte-for-byte the pre-existing
name** — so all v1 tasks, every hosted/local validation condition, and the
existing artifact-distinctness guard are unchanged. `compare-configs` identifies
the two configurations by **source path, labeled by config role**, never by the
shared in-record `condition_id`.

## Considered Options

- **Filename prompt-config tag; record schema frozen** (chosen). The two runs are
  distinguished by *which file they stream to*; the path (not the in-record id) is
  the config identity for the comparison. Zero change to the frozen `RunResult`
  schema, zero change to the v1 artifact contract, and the empty-tag default keeps
  every existing filename and test untouched.
- **Re-stamp a synthetic per-config `condition_id` into every `RunResult`.**
  Rejected: it mutates the serialized record schema (and every v1 trace's
  meaning), forces a migration of the in-record id away from `provider:model`, and
  re-litigates a contract item 001/002 froze — a large blast radius to distinguish
  two files that the filesystem already distinguishes by name.
- **Run the comparison on two *different* models.** Rejected on scope grounds, not
  naming: it would no longer be an *agent-configuration* contrast (model held
  fixed) and would duplicate the multi-condition validation (item 004 §3).

## Consequences

The prompt-config tag is part of the artifact-naming contract going forward: any
tool that parses `runs-*.jsonl` filenames to recover a condition must tolerate the
optional `__<tag>` suffix. Because the in-record `condition_id` deliberately stays
`provider:model`, **the source artifact path — not the record — is the only thing
that distinguishes the two configurations**; a report that loads both files into
one pool keyed by `condition_id` would re-merge them, so `compare-configs` must
keep the two pools separate by their input paths. This is the documented reason
the comparison CLI takes explicit `--config-a` / `--config-b` path arguments
rather than a single conditions list.

**Tag-slug collision surface:** the fixture stem is slugged via `_slug()` before
being appended as `__<tag>`; two fixture stems that differ only in characters
collapsed by the slug regex (e.g. `planning v1` and `planning-v1`) will produce
the same tag and silently overwrite each other's artifacts. Convention: fixture
stems must be distinct after slugging (i.e. after replacing `[^A-Za-z0-9._-]+`
with `-`).
