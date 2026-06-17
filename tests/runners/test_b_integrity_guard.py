def test_render_b_prompt_does_not_reference_the_evaluator_store() -> None:
    from agent_eval_lab.datasets.b_tasks import render_b_prompt

    rendered = render_b_prompt(
        "Build the B-1 report.",
        save_name="m__b-b1-noskill__0000",
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
    )
    # The prompt never names evaluator.toml, evaluator-only, or a golden id
    # (§7 / TRAP 2).
    low = rendered.lower()
    assert "evaluator.toml" not in low
    assert "evaluator-only" not in low
    assert "golden" not in low


def test_bash_allowlist_rejects_non_playwright_binary() -> None:
    from agent_eval_lab.runners.bash_edge import ALLOWED_BINS, parse_argv

    assert "playwright-cli" in ALLOWED_BINS
    # parse_argv accepts the bare cat name (allowlist check is in the executor), but
    # the executor refuses it; assert the allowlist itself excludes shells/cat.
    assert "cat" not in ALLOWED_BINS
    assert "bash" not in ALLOWED_BINS
    assert "sh" not in ALLOWED_BINS
    # A bare `cat evaluator.toml` parses (bare name) but is not allowlisted.
    argv = parse_argv("cat evaluator.toml")
    assert argv == ["cat", "evaluator.toml"]
    assert argv[0] not in ALLOWED_BINS


def test_file_scheme_store_read_is_blocked() -> None:
    from agent_eval_lab.runners.bash_edge import parse_argv

    # The one chat-loop residual vector (§7) — file:// navigation to the store
    # — is closed.
    assert parse_argv("playwright-cli open file:///abs/evaluator.toml") is None
