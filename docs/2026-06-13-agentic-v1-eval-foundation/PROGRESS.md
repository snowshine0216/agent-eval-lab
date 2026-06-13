# PROGRESS — agentic_v1 eval foundation

Legend: ⬜ todo · 🔄 in-progress · ✅ done · ⏭️ pre-completed/skipped · 🚧 partial (blocked sub-scope)

| # | id | spec | grill | plan | branch | impl | drift | ship | verify | pr-review | fix | merge |
|---|----|------|-------|------|--------|------|-------|------|--------|-----------|-----|-------|
| 1 | 001-records-runner | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | 002-experiment-types | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3 | 003-f3-oracle | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | 004-repo-adapter | ⏭️ | ⏭️ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 5 | 005-dset-harness | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | 006-bset-harness | ⏭️ | ⏭️ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 7 | 007-m1-m2-reports | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

`spec`/`grill` are ⏭️ for all items: the source spec is the brainstorm+grill output (§15/§15a/§15b/§18).

## Log
- 2026-06-13 — Preflights all PASS (PREFLIGHT.md). `.env` + node-22 playwright-cli + F-golden staged + MSTR reachable. Run dir + master artifacts written. Mode=backlog, consolidated PR cadence, project=non-web.
- 2026-06-13 — **001 DONE** (merged): records+runner revision. Gates caught VOID-formula over-voting + return-type bug.
- 2026-06-13 — **002 DONE** (merged): experiment types + check-env (live PASS). Gates caught [oracle.b_set] parsing, readback type, self-signed TLS, cost-by-condition.
- 2026-06-13 — **003 DONE** (merged): F3 oracle (node-test, golden-discriminating, D19/D31). Gates caught ET.ParseError gap + node-version guard. Feature branch green (799 w/ node-22). Next: 005 D-set (reachable now) then 004 F1/F2, 007 report+run, 006 B-set.
- 2026-06-13 — **005 DONE** (merged, ahead of 004): D-set harness (bash/playwright-cli agent + FactKeySpec + 15 fact-keys + run-dset). Live: extracted 1.34; grader PASS/FAIL/faithfulness. Gates caught validity-None misclassification (L1) + silent-void (L2) + allowlist-path (N1). Feature branch green (836 node-22 / 828+8 offline). Remaining: 004 F1/F2, 007 report+RUN, 006 B-set.
- 2026-06-13 — **007 DONE** (merged): M1/M2 aggregation + report layer (Clopper-Pearson F, Holm, macro composite, Pareto, validity/void/censoring, fc-v3) + run-m1/report-m1 CLI. Gates caught zero-weight crash (L1) + void-sidecar loss (L2). Whole repo ruff-clean. **5/7 done (001,002,003,005,007).** Report ENGINE complete + verified on synthetic+partial D-only render. REMAINING: 004 F1/F2 (F-domain), 006 B-set (B-domain/M2), and the ACTUAL M1 RUN (real models) — not yet executed.
- 2026-06-13 — **M1 D-domain SCOPED PILOT RUN executed** (Option 1). 3 models launched (15q x k=2); deepseek + minimax completed (30 valid each, pass^k=0.600 both, tie; minimax ~9x cheaper); GLM crashed on SiliconFlow 400 (context-length; run_dset writes-at-end lost its data — robustness gap noted). Report: reports/agentic-v1/M1-final-report.md (gitignored). Frozen specs: M1-spec.frozen.json (k=5 canonical) + M1-pilot-spec.frozen.json (k=2 pilot). HANDOFF.md written. Instrument 5/7; F(004)/B(006) + full k=5 run remain.
