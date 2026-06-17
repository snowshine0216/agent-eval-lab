import json

from agent_eval_lab.runners.playwright_config import render_playwright_cli_config


def test_config_always_ignores_https_errors_and_omits_storage_state_when_absent():
    """The self-signed labs cert must always be tolerated; with no pre-saved
    auth the storageState key is omitted (a fresh, unauthenticated context)."""
    cfg = json.loads(render_playwright_cli_config())
    ctx = cfg["browser"]["contextOptions"]
    assert ctx["ignoreHTTPSErrors"] is True
    assert "storageState" not in ctx


def test_config_pins_storage_state_when_a_path_is_given():
    """A pre-saved bxu login is loaded so the candidate's first `open` is
    already authenticated (spec §6.2)."""
    cfg = json.loads(
        render_playwright_cli_config(storage_state_path="/store/bxu-auth.json")
    )
    ctx = cfg["browser"]["contextOptions"]
    assert ctx["storageState"] == "/store/bxu-auth.json"
    assert ctx["ignoreHTTPSErrors"] is True
