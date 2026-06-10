"""EDGE: command-line orchestration. All logic lives in the pure core."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

import httpx

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.serialize import run_result_to_dict
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown
from agent_eval_lab.runners.config import PROVIDERS, ProviderConfig, condition_id
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.tasks.loader import load_tasks
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
    results = tuple(
        run
        for task in tasks
        for run in run_task_k(
            task=task,
            registry=WORKSPACE_TOOLS,
            config=config,
            http_client=http_client,
            k=k,
            max_steps=max_steps,
            temperature=temperature,
        )
    )
    report = build_baseline_report(
        results,
        dataset_id=dataset_path.stem,
        condition_id=condition_id(config),
        k=k,
        price=price,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / f"runs-{config.id}.jsonl"
    runs_path.write_text(
        "\n".join(json.dumps(run_result_to_dict(run)) for run in results) + "\n"
    )
    report_path = out_dir / f"baseline-{config.id}.md"
    report_path.write_text(render_markdown(report))
    return report_path


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
    return parser


def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
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
    client = http_client or httpx.Client(timeout=120.0)
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


if __name__ == "__main__":
    raise SystemExit(main())
