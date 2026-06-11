"""EDGE: command-line orchestration. All logic lives in the pure core."""

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import TextIO

import httpx

from agent_eval_lab.calibrate.packet import (
    build_packet,
    compute_agreement,
    import_packet,
    packet_to_jsonl,
    render_agreement_report,
)
from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import run_result_to_dict, trajectory_from_dict
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown
from agent_eval_lab.reports.comparison import build_comparison_report
from agent_eval_lab.reports.comparison import render_markdown as render_comparison
from agent_eval_lab.reports.validation import ConditionInput, build_validation_report
from agent_eval_lab.reports.validation import render_markdown as render_validation
from agent_eval_lab.runners.config import (
    PROVIDERS,
    ProviderConfig,
    condition_id,
    resolve_proxy,
)
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.runners.worlds import resolve_world
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import LlmJudgeSpec


def run_baseline(
    *,
    dataset_path: Path,
    config: ProviderConfig,
    k: int,
    max_steps: int,
    temperature: float,
    out_dir: Path,
    price: TokenPrice | None,
    http_client: httpx.Client,
    system_prompt: str | None = None,
    system_prompt_path: Path | None = None,
) -> Path:
    tasks = load_tasks(dataset_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    condition = condition_id(config)
    slug = _slug(condition) + _prompt_config_tag(system_prompt_path)
    results: list[RunResult] = []
    with (out_dir / f"runs-{slug}.jsonl").open("w") as runs_file:
        for task in tasks:
            binding = resolve_world(task.input.available_tools)
            run_task = (
                task
                if system_prompt is None
                else replace(
                    task,
                    input=replace(
                        task.input,
                        messages=apply_system_prompt(
                            task.input.messages, system_prompt
                        ),
                    ),
                )
            )
            task_runs = run_task_k(
                task=run_task,
                registry=binding.registry,
                config=config,
                http_client=http_client,
                k=k,
                max_steps=max_steps,
                temperature=temperature,
                apply_fn=binding.apply_fn,
                executor=binding.executor,
            )
            _append_runs(runs_file, task_runs)
            results.extend(task_runs)
    report = build_baseline_report(
        tuple(results),
        dataset_id=dataset_path.stem,
        condition_id=condition,
        k=k,
        price=price,
    )
    report_path = out_dir / f"baseline-{slug}.md"
    report_path.write_text(render_markdown(report))
    return report_path


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically: write to a sibling tmp file in the same
    directory then os.replace so a crash never leaves a partial file at the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _prompt_config_tag(system_prompt_path: Path | None) -> str:
    """ADR-0007: empty tag (byte-identical v1 name) when no override is given;
    otherwise '__<fixture-stem>'. The stem is slugged like the condition id."""
    if system_prompt_path is None:
        return ""
    return f"__{_slug(system_prompt_path.stem)}"


def _slug(condition: str) -> str:
    """Filesystem-safe artifact name: condition ids contain ':' and may
    contain '/' (e.g. openrouter model ids)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", condition)


def _append_runs(runs_file: TextIO, runs: Sequence[RunResult]) -> None:
    runs_file.write("".join(json.dumps(run_result_to_dict(run)) + "\n" for run in runs))
    runs_file.flush()


# The canonical judge spec the calibration corpus is scored on (scale 1-5). All
# CLI calibrate handlers pass this to build_packet so the packet records the scale.
_CALIBRATION_SPEC = LlmJudgeSpec(
    rubric="(see examples/calibration/rubric.md)",
    judge_model="(calibration)",
    scale=(1, 5),
)


def _load_calibration_fixtures(path: Path) -> list[tuple[str, object]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [(row["id"], trajectory_from_dict(row["trajectory"])) for row in rows]


def _load_run_results(path: Path) -> list[RunResult]:
    runs: list[RunResult] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            g = row["grade"]
            runs.append(
                RunResult(
                    task_id=row["task_id"],
                    condition_id=row["condition_id"],
                    run_index=row["run_index"],
                    trajectory=trajectory_from_dict(row["trajectory"]),
                    grade=GradeResult(
                        grader_id=g["grader_id"],
                        passed=g["passed"],
                        score=g["score"],
                        evidence=g["evidence"],
                        failure_reason=g["failure_reason"],
                    ),
                )
            )
        except Exception as exc:
            raise ValueError(
                f"malformed record in {path} at line {lineno} "
                f"({len(runs)} records loaded so far)"
            ) from exc
    return runs


def _capability_map(dataset_path: Path) -> dict[str, str]:
    tasks = load_tasks(dataset_path)
    return {t.id: t.capability for t in tasks}


def _parse_runs_spec(spec: str) -> tuple[str, Path]:
    """'LABEL=condition_id=path' or 'LABEL=path'. Returns (label, path).

    The condition_id may itself contain '=' (e.g. openrouter model ids).
    Parse left-to-right for LABEL with split("=", 1), then right-to-left for
    PATH with rsplit("=", 1) on the remainder — condition keeps any interior '='.
    """
    label_rest = spec.split("=", 1)
    if len(label_rest) < 2:
        raise ValueError(f"bad --runs spec {spec!r}; want LABEL=condition_id=path")
    label, rest = label_rest
    # rest is either 'condition_id=path' or just 'path'
    # rsplit("=", 1) gives ['condition_or_bare', 'path'] or ['path'] if no '='
    cond_or_path, *tail = rest.rsplit("=", 1)
    if tail:
        return label, Path(tail[0])
    return label, Path(cond_or_path)


def _hosted_label(label: str) -> bool:
    return label.upper() in {"C1", "C2", "C3"}


def _run_report_validation(args: argparse.Namespace) -> int:
    tiers = json.loads(args.tiers.read_text())
    caps = _capability_map(args.dataset)
    conditions = []
    for spec in args.runs:
        try:
            label, path = _parse_runs_spec(spec)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        results = _load_run_results(path) if path.exists() else []
        conditions.append(
            ConditionInput(
                label=label,
                results=results,
                hosted=_hosted_label(label),
                blocked_reason=None if results else "no reachable records",
            )
        )
    report = build_validation_report(
        conditions=tuple(conditions),
        tiers=tiers,
        capabilities=caps,
        k=args.k,
        expected_n_tasks=args.expected_n_tasks,
        seed=args.seed,
        n_resamples=args.n_resamples,
        alpha=args.alpha,
    )
    _atomic_write(args.out, render_validation(report))
    print(args.out)
    return 0


def _run_compare_configs(args: argparse.Namespace) -> int:
    # P1-7b: explicit missing-file check with a clean message.
    for label, path in (("--config-a", args.config_a), ("--config-b", args.config_b)):
        if not path.exists():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            return 1
    tiers = json.loads(args.tiers.read_text())
    results_a = _load_run_results(args.config_a)
    results_b = _load_run_results(args.config_b)
    # P1-7c: detect empty hard-subset before calling the pure core.
    hard_a = [r for r in results_a if tiers.get(r.task_id) in ("T3", "T4")]
    hard_b = [r for r in results_b if tiers.get(r.task_id) in ("T3", "T4")]
    if not hard_a or not hard_b:
        print(
            f"error: no T3/T4 tasks found for the primary comparison "
            f"(check --tiers file: {args.tiers})",
            file=sys.stderr,
        )
        return 1
    # P1-7a: catch universe-mismatch ValueError from the pure core and emit a
    # clean one-line diagnostic (no traceback).
    try:
        report = build_comparison_report(
            results_a=results_a,
            results_b=results_b,
            tiers=tiers,
            planning_prompt_text=args.planning_prompt_file.read_text(),
            config_a_path=str(args.config_a),
            config_b_path=str(args.config_b),
            k=args.k,
            seed=args.seed,
            n_resamples=args.n_resamples,
            alpha=args.alpha,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _atomic_write(args.out, render_comparison(report))
    print(args.out)
    return 0


def _render_packet_markdown(packet) -> str:
    lines = [
        f"# Annotation packet ({packet.packet_format} / {packet.rubric_version})",
        "",
        packet.rubric,
        "",
        "Score each item 1-5 per the rubric, then fill the JSONL `score` field.",
        "",
    ]
    for item in packet.items:
        lines += [
            f"## {item.fixture_id}",
            "```",
            item.trajectory_digest,
            "```",
            "score: ____",
            "",
        ]
    return "\n".join(lines) + "\n"


def _run_export_packet(args: argparse.Namespace) -> int:
    fixtures = _load_calibration_fixtures(args.fixtures)
    rubric = args.rubric.read_text()
    packet = build_packet(fixtures=fixtures, spec=_CALIBRATION_SPEC, rubric=rubric)
    _atomic_write(args.out, packet_to_jsonl(packet))
    _atomic_write(args.out.with_suffix(".md"), _render_packet_markdown(packet))
    print(args.out)
    return 0


def _run_compute(args: argparse.Namespace) -> int:
    fixtures = _load_calibration_fixtures(args.fixtures)
    blank = build_packet(
        fixtures=fixtures, spec=_CALIBRATION_SPEC, rubric=args.rubric.read_text()
    )
    packets = [import_packet(p.read_text(), expected=blank) for p in args.packets]
    report = compute_agreement(
        packets,
        threshold=4,
        scale=(1, 5),
        seed=args.seed,
        n_resamples=args.n_resamples,
        alpha=args.alpha,
    )
    md = render_agreement_report(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
        print(args.out)
    else:
        print(md)
    return 0


def _run_provisional_label(args: argparse.Namespace, http_client) -> int:
    from agent_eval_lab.calibrate.provisional import run_provisional_labeling

    config = PROVIDERS[args.provider]
    # D12: pre-flight the key; clean documented skip, never a mid-corpus crash.
    if config.api_key_env and not os.environ.get(config.api_key_env):
        print(
            f"{config.api_key_env} key unset;"
            f" provisional run skipped for {args.provider}"
        )
        return 0
    fixtures = _load_calibration_fixtures(args.fixtures)
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )
    try:
        packet = run_provisional_labeling(
            fixtures=fixtures,
            rubric=args.rubric.read_text(),
            config=config,
            annotator_id=condition_id(config),
            http_client=client,
        )
    finally:
        if http_client is None:
            client.close()
    scored = sum(1 for i in packet.items if i.score is not None)
    errored = sum(1 for i in packet.items if i.score is None)
    print(f"scored={scored} errored={errored} total={len(packet.items)}")
    _atomic_write(args.out, packet_to_jsonl(packet))
    print(args.out)
    return 0


def _run_calibrate(args, parser, http_client):
    if args.calibrate_command == "export-packet":
        return _run_export_packet(args)
    if args.calibrate_command == "compute":
        return _run_compute(args)
    if args.calibrate_command == "provisional-label":
        return _run_provisional_label(args, http_client)
    parser.error(f"unknown calibrate command: {args.calibrate_command}")


def _run_baseline_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    http_client: httpx.Client | None,
) -> int:
    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)
    price = None
    given = (args.input_price_per_mtok, args.output_price_per_mtok)
    if (given[0] is None) != (given[1] is None):
        parser.error(
            "--input-price-per-mtok and --output-price-per-mtok must be given together"
        )
    if given[0] is not None and given[1] is not None:
        price = TokenPrice(input_per_mtok=given[0], output_per_mtok=given[1])
    # trust_env=False so only an explicitly opted-in provider (e.g. openrouter)
    # is proxied; domestic endpoints and localhost stay direct.
    system_prompt = None
    if args.system_prompt_file is not None:
        system_prompt = args.system_prompt_file.read_text()
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )
    try:
        report_path = run_baseline(
            dataset_path=args.dataset,
            config=config,
            k=args.k,
            max_steps=args.max_steps,
            temperature=args.temperature,
            out_dir=args.out,
            price=price,
            http_client=client,
            system_prompt=system_prompt,
            system_prompt_path=args.system_prompt_file,
        )
    except httpx.TransportError as exc:
        # Criterion 5: a connection failure is a one-line exit-1 diagnostic —
        # never a traceback mid-corpus. The streamed JSONL keeps any partial
        # progress for `incomplete` reporting.
        hint = " — is the server running?" if config.id == "local" else ""
        print(
            f"error: cannot reach provider {config.id!r} at {config.base_url} "
            f"({type(exc).__name__}: {exc}){hint}",
            file=sys.stderr,
        )
        return 1
    finally:
        if http_client is None:
            client.close()
    print(report_path)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-eval-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline = subparsers.add_parser("run-baseline", help="run the baseline eval")
    baseline.add_argument("--dataset", required=True, type=Path)
    baseline.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    baseline.add_argument("--model", help="override the provider's default model id")
    baseline.add_argument("--k", type=int, default=3)
    baseline.add_argument("--max-steps", type=int, default=6)
    baseline.add_argument("--temperature", type=float, default=0.0)
    baseline.add_argument("--out", type=Path, default=Path("reports"))
    baseline.add_argument("--input-price-per-mtok", type=float)
    baseline.add_argument("--output-price-per-mtok", type=float)
    baseline.add_argument(
        "--system-prompt-file",
        type=Path,
        help="override each task's system turn with this file's text (Config B); "
        "tags the artifact slug with __<file-stem> (ADR-0007)",
    )

    calibrate = subparsers.add_parser("calibrate", help="judge calibration harness")
    cal_sub = calibrate.add_subparsers(dest="calibrate_command", required=True)

    export = cal_sub.add_parser("export-packet", help="write a blind annotation packet")
    export.add_argument("--fixtures", required=True, type=Path)
    export.add_argument("--rubric", required=True, type=Path)
    export.add_argument("--out", required=True, type=Path)

    compute = cal_sub.add_parser(
        "compute", help="compute human-human kappa from filled packets"
    )
    compute.add_argument("--packets", required=True, nargs="+", type=Path)
    compute.add_argument("--fixtures", required=True, type=Path)
    compute.add_argument("--rubric", required=True, type=Path)
    compute.add_argument("--out", type=Path)
    compute.add_argument("--seed", type=int, default=20260610)
    compute.add_argument("--n-resamples", type=int, default=2000)
    compute.add_argument("--alpha", type=float, default=0.05)

    prov = cal_sub.add_parser(
        "provisional-label",
        help="LLM annotator blind-scores fixtures (PROVISIONAL)",
    )
    prov.add_argument("--fixtures", required=True, type=Path)
    prov.add_argument("--rubric", required=True, type=Path)
    prov.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    prov.add_argument("--out", required=True, type=Path)

    rv = subparsers.add_parser(
        "report-validation", help="rebuild the failure-mode report from JSONL (pure)"
    )
    rv.add_argument(
        "--runs",
        required=True,
        nargs="+",
        help="one per condition: LABEL=condition_id=path/to/runs-*.jsonl",
    )
    rv.add_argument("--dataset", required=True, type=Path)
    rv.add_argument("--tiers", required=True, type=Path)
    rv.add_argument("--k", type=int, default=3)
    rv.add_argument("--expected-n-tasks", type=int, default=50)
    rv.add_argument("--out", required=True, type=Path)
    rv.add_argument("--seed", type=int, default=20260610)
    rv.add_argument("--n-resamples", type=int, default=2000)
    rv.add_argument("--alpha", type=float, default=0.05)

    cc = subparsers.add_parser(
        "compare-configs", help="rebuild the two-config comparison from JSONL (pure)"
    )
    cc.add_argument("--config-a", required=True, type=Path)
    cc.add_argument("--config-b", required=True, type=Path)
    cc.add_argument("--tiers", required=True, type=Path)
    cc.add_argument("--planning-prompt-file", required=True, type=Path)
    cc.add_argument("--k", type=int, default=3)
    cc.add_argument("--out", required=True, type=Path)
    cc.add_argument("--seed", type=int, default=20260610)
    cc.add_argument("--n-resamples", type=int, default=2000)
    cc.add_argument("--alpha", type=float, default=0.05)

    return parser


def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "calibrate":
        return _run_calibrate(args, parser, http_client)
    if args.command == "report-validation":
        return _run_report_validation(args)
    if args.command == "compare-configs":
        return _run_compare_configs(args)
    return _run_baseline_command(args, parser, http_client)


if __name__ == "__main__":
    raise SystemExit(main())
