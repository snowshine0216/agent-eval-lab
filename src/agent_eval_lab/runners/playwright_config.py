"""PURE: the ``.playwright/cli.config.json`` text for the live B-set browse path.

playwright-cli auto-loads ``.playwright/cli.config.json`` from its CWD (the
per-trial workdir). Two facts about the MicroStrategy labs host must be pinned
there, because the confined candidate cannot pass them on the command line:

- ``ignoreHTTPSErrors`` — the labs host serves a self-signed cert; without this
  every ``open`` fails ``ERR_CERT_AUTHORITY_INVALID`` (calibration 2026-06-17).
- ``storageState`` — a pre-saved ``bxu`` login (cookies: iSession/JSESSIONID)
  so the candidate's ``open`` lands in an ALREADY-authenticated app, matching
  the prompt's "the session is already authenticated for you" (spec §6.2). The
  credential never enters the model context (§7 integrity boundary).
"""

import json


def render_playwright_cli_config(
    *, storage_state_path: str | None = None, ignore_https_errors: bool = True
) -> str:
    """Render the cli.config.json text. PURE.

    ``storageState`` is included only when a path is given (an absent path means
    a fresh, unauthenticated context). Both keys live under
    ``browser.contextOptions`` (playwright BrowserContextOptions).
    """
    context_options: dict[str, object] = {"ignoreHTTPSErrors": ignore_https_errors}
    if storage_state_path:
        context_options["storageState"] = storage_state_path
    return json.dumps({"browser": {"contextOptions": context_options}}, indent=2)
