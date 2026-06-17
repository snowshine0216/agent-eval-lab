# B-set live candidate authenticates via a pre-saved playwright storageState

The B-1 spike prompt tells the candidate "the session is **already authenticated** for you; do
not ask for or print credentials" (`render_b_prompt`, spec §6.2 / §7) — the credential must
**never enter the model context**. But the chat driver opens a **fresh** playwright-cli session
per trial, and the claude -p driver runs in a fresh temp workdir, so neither session carries any
auth by default. The first live calibration (2026-06-17, deepseek noskill) confirmed the gap:
the candidate hit the real MSTR login form, fought a self-signed cert (`ERR_CERT_AUTHORITY_INVALID`),
and — never told `bxu` is passwordless — **hallucinated a password** (`MicroStrategy1`), burning all
50 rounds before login. The "already authenticated" contract was aspirational, not wired.

**Decision:** the live browse path is pre-authenticated **out-of-band** via a pre-saved playwright
**storageState** (the `bxu` login: `iSession` / `JSESSIONID` cookies), injected through a per-trial
`.playwright/cli.config.json` that playwright-cli auto-loads from its CWD. A new pure renderer
(`runners/playwright_config.py: render_playwright_cli_config`) emits that config with
`browser.contextOptions.ignoreHTTPSErrors = true` (the self-signed labs cert) plus
`storageState = <path>` when a pre-saved login is configured (`[candidate] storage_state`). **Both**
candidate drivers write this file into the session workdir **before** the browse loop / `claude -p`
launch, so the candidate's first `open` lands in an already-authenticated app — the credential is
established by the operator's one-time `state-save`, never by the model. Validated end-to-end the
same day: a fresh context loading the saved state opens `/app` authenticated (`login: false`), and a
150-round re-calibration showed `0` login-page hits across ~12 minutes.

## Considered Options

- **Pre-saved storageState injected via `.playwright/cli.config.json`** (chosen). One config file
  fixes the cert **and** the auth in one place; works for both the chat and claude drivers; keeps
  §7 intact — no credential reaches the model context (`render_b_prompt` still omits the password).
  The storageState is a static snapshot, so it must be **regenerated before each sweep** (MSTR
  sessions expire) — recorded in the runbook.
- **Tell the model to log in as `bxu` with an empty password** (prompt change). Rejected as the
  primary mechanism: it contradicts the "already authenticated" contract, spends rounds logging in
  every trial, and (though `bxu` is passwordless so nothing leaks) normalizes putting login steps in
  the model context. Kept only as a fallback for a future password-bearing candidate.
- **A persistent `userDataDir` profile** shared across trials. Rejected for the spike: it locks the
  profile to one browser at a time and accumulates cross-trial state; storageState is read-only,
  copyable, and per-trial-clean. (Left as the escalation path if a candidate's auth ever lands in
  `sessionStorage`, which storageState does not capture — MSTR's does not, verified.)

## Consequences

`[candidate] storage_state` (a path to the pre-saved login) is the new operator precondition for a
live `run-b`; absent it, the candidate opens unauthenticated and every trial censors at login. The
cert-ignore half is unconditional (the labs host is always self-signed). The claude -p driver shares
the exact same config write, so its `open` is authenticated too — but the driver still records **no
trajectory** (only `num_turns`/cost), so a claude trial's progress is **not observable** from the
artifact; success must be read from MSTR state (the saved object) or by adding trajectory capture.
The storageState's expiry bounds a sweep's wall-clock — long sweeps must regenerate it between models
and watch for `login-page` hits as the expiry signal.
