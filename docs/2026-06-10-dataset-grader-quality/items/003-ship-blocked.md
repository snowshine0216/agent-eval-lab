# Ship-blocking findings (steps 8+9 review) — round 1

P0-1 compute_agreement accepts unscored (None) items: crash (binary path) or
None==None counted as agreement (poisoned κ). Guard with structured error;
also reject ≠2 packets explicitly; weighted_kappa KeyError on out-of-category
labels → structured error.
P0-2 JudgeError grades passed=False with failure_reason=None and (verify)
evidence may not mark infra-vs-agent. Evidence must carry an explicit
judge_error marker; pin with tests; document infra-vs-agent reading in runbook.
P1-3 Packet writes not atomic (truncation masquerades as id-mismatch) → tmp+rename.
P1-4 Provisional run with partial judge errors exits 0 silently → print
scored/errored counts; include error count in summary.
P1-5 parse permissiveness unpinned: lowercase "score: 4" accepted (document+pin);
bold/float fail-safe (pin).
P1-6 (reputational) all 9 unfaithful fixtures are gross violations → κ=0.862
partly reflects case easiness. Add 4 near-miss boundary fixtures (cf-17..20),
re-run provisional, regenerate summary with honest difficulty-profile section.
