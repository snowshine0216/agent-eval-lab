# Ship-blocking findings (steps 8+9 review) — round 1

Arithmetic: all committed numbers recomputed exact (C3 0.980/0.940; C4
0.620/0.620; C4-T3 7/22=0.318; Config B 49/50, ws2-014 T2 fail; primary
Δ CI [0,0] valid).

P0-1 _parse_runs_spec splits "=" from the left → condition ids containing
"=" silently load the wrong path and render as blocked. rsplit fix + test.
P0-2 JSONL malformed/truncated line → raw traceback without file/line
context (still must fail loud — add context, never skip).
P1-3 pass^k vacuous all() on tasks with <k runs → inflation on partial
streams; report layer must exclude deficit tasks with an explicit count.
P1-4 "strong" discriminativeness rung satisfied by ceiling-flat monotone
gradients — oversell. Tighten: gradient rung requires a strict decrease;
verdict must name its evidence. Expected new verdict: weak rung met (local
decisively separated, CI excludes 0), strong not met (hosted Δ −0.06 CI
touches 0 at n=50). Regenerate committed reports after.
P1-5 capability map "?" fallback silently mislabels taxonomy → raise like
tier_of.
P1-6 _task_reliability duplicated (validation.py vs reliability.py) →
import one definition.
P1-7 compare-configs UX: universe-mismatch and missing-file errors surface
as raw tracebacks; n_tasks header from A only; empty hard-subset crash
message; discriminativeness silently skips mismatched-universe pairs.
NOTE-8 prompt-config tag slug collisions — documented in ADR-0007, no code.
