"""EDGE: command-line orchestration. All logic lives in the pure core."""

import argparse
import json
import os
import re
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
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.serialize import run_result_to_dict, trajectory_from_dict
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown
from agent_eval_lab.runners.config import (
    PROVIDERS,
    ProviderConfig,
    condition_id,
    resolve_proxy,
)
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import LlmJudgeSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


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
) -> Path:
    tasks = load_tasks(dataset_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    condition = condition_id(config)
    slug = _slug(condition)
    results: list[RunResult] = []
    with (out_dir / f"runs-{slug}.jsonl").open("w") as runs_file:
        for task in tasks:
            task_runs = run_task_k(
                task=task,
                registry=WORKSPACE_TOOLS,
                config=config,
                http_client=http_client,
                k=k,
                max_steps=max_steps,
                temperature=temperature,
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
        )
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

    return parser


def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "calibrate":
        return _run_calibrate(args, parser, http_client)
    return _run_baseline_command(args, parser, http_client)


if __name__ == "__main__":
    raise SystemExit(main())
