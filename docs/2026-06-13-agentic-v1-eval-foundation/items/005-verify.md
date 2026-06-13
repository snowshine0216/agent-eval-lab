# Item 005 — D-set Harness Verify

**VERDICT: PASS**

Verified 2026-06-13. Scratch script at `/tmp/verify_005.py` (not in repo).
All 6 checks executed end-to-end without a paid model API.

---

## Environment

```
playwright-cli  0.1.14   /Users/snow/.nvm/versions/node/v22.22.2/bin/playwright-cli
node            v22.22.2
uv              (project venv, Python 3.13.12)
docs URL        http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html  HTTP 200
```

---

## Check 1 — Live browse via the bash edge: `playwright-cli` runs, `1.34` captured

The bash executor (`runners/bash_edge.py::make_bash_executor`) was called directly with two `BashRequest` effect-requests: `open` then `eval "() => document.body.innerText"`.

```
RUNNING: 'playwright-cli -s=verify-005-c1 open http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html'
exit_code=0, timed_out=False
stdout: "### Browser `verify-005-c1` opened with pid 39797.\n### Ran Playwright code\n```js\nawait page.goto('http://<CMC_DOCS_HOST>/...');\n```\n..."

RUNNING: 'playwright-cli -s=verify-005-c1 eval "() => document.body.innerText"'
exit_code=0, timed_out=False
page text length: 8162 chars
FOUND '1.34' at char 7984:
  ...'27\nStrategy ONE\tJuly 2026\tReference\nKubernetes Cluster\t1.34\tReference\nFile Storage\tSupport NFS/Ceph Protocol\nSupport RWX mode\tBase'...
```

The executor used `shell=False` (Popen with argv list), ran the allowlisted binary `playwright-cli` from the node-22 bin dir, and captured stdout. `1.34` is on the live page at the Support Matrix row `Kubernetes Cluster\t1.34\tReference`.

**PASS**

---

## Check 2 — FactKeySpec grades CORRECT answer PASS

Q2 spec: `required=["1.34"]`, `forbidden=["1.32","1.33","1.30","1.28"]`.  
Answer: `"…the recommended Kubernetes version is 1.34. This is the version validated for CMC deployments."`

```python
GradeResult:
  grader_id = 'fact_key'
  passed    = True
  score     = 1.0
  evidence  = {
    'level': 1,
    'required_not_on_page': [],
    'missing_required': [],
    'present_forbidden': [],
    'page_snapshot_sha256': '4e02589db2144c9b88780e81dec202bdf1d94ac7c09899ff376240e67971abdf'
  }
```

**PASS**

---

## Check 3 — FactKeySpec grades WRONG answer FAIL

Same Q2 spec. Answer: `"…the recommended Kubernetes version is 1.32. This is the validated version."`  
`1.32` is in `forbidden`; `1.34` is missing from the answer.

```python
GradeResult:
  grader_id = 'fact_key'
  passed    = False
  score     = 0.0
  evidence  = {
    'level': 1,
    'required_not_on_page': [],
    'missing_required': ['1.34'],
    'present_forbidden': ['1.32'],
    'page_snapshot_sha256': '4e02589db2144c9b88780e81dec202bdf1d94ac7c09899ff376240e67971abdf'
  }
```

**PASS**

---

## Check 4 — Faithfulness gate: required key absent from page snapshot → FAIL

A synthetic spec with `required=["1.99"]` and a `page_snapshot` that contains only `"The recommended Kubernetes version is 1.34 per the Support Matrix."`. The answer states `"The recommended version is 1.99"` — `1.99` is in the answer but NOT on the page.

```python
GradeResult:
  grader_id              = 'fact_key'
  passed                 = False
  score                  = 0.0
  required_not_on_page   = ['1.99']
  missing_required       = []
  present_forbidden      = []
```

The faithfulness gate (`required_not_on_page`) fires. `passed=False` because `1.99` is not a substring of the page snapshot. The candidate's answer stated a plausible-looking fact that the authoritative page does not contain.

**PASS**

---

## Check 5 — D19 no-leak: candidate Task has no fact-keys/answers

`build_cmc_tasks` was called; `tasks[1]` (cmc-q02) was inspected.

```
Task id:         cmc-q02
capability:      docs_qa
available_tools: ('bash',)

TaskInput messages:
  [system]: "You are answering documentation questions about Strategy Customer
             Managed Cloud (CMC). You have a single tool: `bash`. Use it to
             drive a headless browser via playwright-cli…"
  [user]:   "From the Support Matrix, find the recommended Kubernetes version
             and explain in one short sentence why that value is important for
             someone planning a deployment."

Fact-key check against candidate text:
  required key '1.34':  ABSENT ✓
  forbidden key '1.32': ABSENT ✓
  forbidden key '1.33': ABSENT ✓
  forbidden key '1.30': ABSENT ✓
  forbidden key '1.28': ABSENT ✓

verification type: FactKeySpec
(Not in TaskInput.messages → evaluation-only)

Q2 user message: 'From the Support Matrix, find the recommended Kubernetes
                  version and explain in one short sentence why that value is
                  important for someone planning a deployment.'
'1.34' in user message: False ← no leak
```

The `FactKeySpec` (required/forbidden lists + page snapshot) lives only in `task.verification`, which is the evaluation-only field. Nothing in `TaskInput.messages` or `available_tools` reveals any answer key.

**PASS**

---

## Check 6 — D-set builds 15 tasks

```
build_cmc_tasks returned 15 tasks

cmc-q01  capability=docs_qa  split=held_out  difficulty=L1  verif=FactKeySpec
cmc-q02  capability=docs_qa  split=held_out  difficulty=L1  verif=FactKeySpec
cmc-q03  capability=docs_qa  split=held_out  difficulty=L1  verif=FactKeySpec
cmc-q04  capability=docs_qa  split=held_out  difficulty=L2  verif=FactKeySpec
cmc-q05  capability=docs_qa  split=held_out  difficulty=L2  verif=FactKeySpec
cmc-q06  capability=docs_qa  split=held_out  difficulty=L2  verif=FactKeySpec
cmc-q07  capability=docs_qa  split=held_out  difficulty=L3  verif=FactKeySpec
cmc-q08  capability=docs_qa  split=held_out  difficulty=L3  verif=FactKeySpec
cmc-q09  capability=docs_qa  split=held_out  difficulty=L3  verif=FactKeySpec
cmc-q10  capability=docs_qa  split=held_out  difficulty=L4  verif=AllOf
cmc-q11  capability=docs_qa  split=held_out  difficulty=L4  verif=AllOf
cmc-q12  capability=docs_qa  split=held_out  difficulty=L4  verif=AllOf
cmc-q13  capability=docs_qa  split=held_out  difficulty=L5  verif=AllOf
cmc-q14  capability=docs_qa  split=held_out  difficulty=L5  verif=AllOf
cmc-q15  capability=docs_qa  split=held_out  difficulty=L5  verif=AllOf

Q1–Q9:   FactKeySpec  (deterministic floor, headline)
Q10–Q15: AllOf(FactKeySpec floor + LlmJudgeSpec stub, reported-only)
```

**PASS**

---

## Test suite

**With node-22 on PATH:**

```
836 passed in 22.93s
```

(Earlier in the session a parallel full-suite run showed 2 failures in
`tests/runners/test_pytest_edge.py::test_run_pytest_cleans_up_its_sandbox` and
`test_run_pytest_timeout_is_structured_and_reaped`. These are pre-existing
process-cleanup timing flakes: both pass immediately when the file is run alone
(`39 passed in 2.40s`), and both passed on the subsequent full-suite rerun.
They are not regressions from item 005.)

**Without node-22 on PATH** (`PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/local/bin`):

```
828 passed, 8 skipped in 21.41s
```

The 8 skipped tests are the live/node-gated tests that require `playwright-cli`
(bash edge integration + live-browse tests). They skip cleanly rather than fail
when node-22 is absent from PATH, confirming the skip guards work.

---

## Summary

| Check | Result |
|-------|--------|
| 1 — Live browse via bash edge, `1.34` extracted | PASS |
| 2 — FactKeySpec grades correct answer PASS | PASS |
| 3 — FactKeySpec grades wrong answer FAIL | PASS |
| 4 — Faithfulness gate (hallucinated key absent from page) FAIL | PASS |
| 5 — D19 no-leak: candidate Task shows no fact-keys | PASS |
| 6 — D-set builds 15 tasks (cmc-q01…cmc-q15) | PASS |
| Suite with node-22 | 836 passed |
| Suite without node-22 | 828 passed, 8 skipped |
