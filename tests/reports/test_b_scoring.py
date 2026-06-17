from agent_eval_lab.records.b_trial import BTrial
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.b_scoring import emit_verdict_sheet


def _trial(*, task_id, save_name, stop_reason, rounds, max_rounds_bound=False):
    return BTrial(
        run_uid=f"c__{task_id}__0000",
        condition_id="dashscope:qwen3.7-max",
        task_id=task_id,
        save_name=save_name,
        folder="/Candidate/bxu",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=2.0),
            run_index=0,
            stop_reason=stop_reason,
            rounds=rounds,
            wall_time_s=12.5,
            max_rounds_bound=max_rounds_bound,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_verdict_sheet_carries_checklist_and_blank_verdict_column() -> None:
    md, csv = emit_verdict_sheet(
        [
            _trial(
                task_id="b-b1-noskill",
                save_name="s0",
                stop_reason="completed_natural",
                rounds=7,
            )
        ]
    )
    # The definition-match checklist R1..R5 is at the top of the markdown sheet.
    for marker in ("R1", "R2", "R3", "R4", "R5"):
        assert marker in md
    # One row per trial, a blank verdict column header, and the instructed save-name.
    assert "verdict" in md.lower()
    assert "s0" in md
    assert "b-b1-noskill" in md
    # CSV header includes save_name + a blank verdict column.
    header = csv.splitlines()[0]
    assert "save_name" in header
    assert "verdict" in header


def test_verdict_sheet_csv_quoting_survives_comma_in_field() -> None:
    """P1-2: a field containing a comma (e.g. a folder path that includes a comma)
    must be quoted correctly so the CSV parses back to the right column count."""
    import csv as csv_mod
    import io

    trial = _trial(
        task_id="b-b1-noskill",
        save_name="s0",
        stop_reason="completed_natural",
        rounds=3,
    )
    # Patch the folder via a fresh BTrial with a comma in the folder value.
    trial_with_comma = BTrial(
        run_uid=trial.run_uid,
        condition_id=trial.condition_id,
        task_id=trial.task_id,
        save_name=trial.save_name,
        folder="/Candidate/bxu,extra",  # comma in folder
        trajectory=trial.trajectory,
        invalid=trial.invalid,
        invalid_reason=trial.invalid_reason,
    )
    _, csv_text = emit_verdict_sheet([trial_with_comma])
    reader = csv_mod.reader(io.StringIO(csv_text))
    n_cols = len(next(reader))  # header row column count
    for row in reader:
        if row:  # skip blank trailing line
            assert len(row) == n_cols, f"column count mismatch: {row!r}"


def test_verdict_sheet_flags_max_rounds_censored_distinctly() -> None:
    md, csv = emit_verdict_sheet(
        [
            _trial(
                task_id="b-b1-noskill",
                save_name="s_capped",
                stop_reason="max_rounds",
                rounds=50,
                max_rounds_bound=True,
            )
        ]
    )
    # A max_rounds cap is surfaced as a censored task-failure, distinct from clean stop.
    assert "censored" in md.lower()
    assert "max_rounds (censored)" in md or "max_rounds(censored)" in md.replace(
        " ", ""
    )
