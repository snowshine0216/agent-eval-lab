# Ship-blocking findings (step 9 adversarial review) — round 1

P0 — phantom-leaf false FAIL in OnlyModifies:
`_leaf_paths` (src/agent_eval_lab/graders/policy.py) represents an empty
Mapping as a leaf `{prefix: {}}` when nested (but `{}` at root), so
`initial_state={"tickets": {}}` + agent correctly writing only
`tickets.T-1.*` yields phantom changed-path "tickets", which
`_is_covered("tickets", ("tickets.T-1",))` rejects → passed=False.
False FAIL = wrong grade = suppressed pass^k. Repro:
OnlyModifies(paths=("tickets.T-1",)), initial {"tickets": {}},
final {"tickets": {"T-1": {"status": "closed"}}} → must PASS, currently FAILs.
Also fixes the root-vs-nested asymmetry P1.
