"""EDGE: command-line orchestration. All logic lives in the pure core."""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, replace
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
from agent_eval_lab.datasets.f_tasks import build_f_tasks
from agent_eval_lab.experiments.ablation_order import ARMS, RunUnit, ablation_run_order
from agent_eval_lab.experiments.evaluator_config import (
    health_probe,
    load_evaluator_config,
)
from agent_eval_lab.experiments.f_ablation_roster import load_f_ablation_roster
from agent_eval_lab.experiments.f_ablation_spec import (
    ABLATION_SEED,
    build_f_ablation_spec,
)
from agent_eval_lab.experiments.m1_run import run_m1
from agent_eval_lab.experiments.pricing import load_pricing
from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
    PlannedComparison,
)
from agent_eval_lab.experiments.spec_hash import freeze_spec as _freeze_spec_pure
from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.grade import GradeResult, RunResult, is_env_invalid_run
from agent_eval_lab.records.serialize import run_result_to_dict, trajectory_from_dict
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown
from agent_eval_lab.reports.comparison import build_comparison_report
from agent_eval_lab.reports.comparison import render_markdown as render_comparison
from agent_eval_lab.reports.final import FinalConditionInput, build_final_report
from agent_eval_lab.reports.final import render_markdown as render_final
from agent_eval_lab.reports.m1 import build_m1_report
from agent_eval_lab.reports.m1 import render_markdown as render_m1
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.reports.validation import ConditionInput, build_validation_report
from agent_eval_lab.reports.validation import render_markdown as render_validation
from agent_eval_lab.runners.claude_cli_candidate import (
    BaselineRow,
    make_claude_run_fn,
    summarize_baseline,
)
from agent_eval_lab.runners.config import (
    PROVIDERS,
    ProviderConfig,
    condition_id,
    resolve_proxy,
)
from agent_eval_lab.runners.f_candidate import (
    build_candidate_tree,
    grade_f_attempt,
    make_edit_task,
    make_f_run_fn,
    run_f_candidate,
)
from agent_eval_lab.runners.multi_run import (
    ReplacementOutcome,
    TrialAttempt,
    run_task_k,
)
from agent_eval_lab.runners.node_edge import node_supports_junit
from agent_eval_lab.runners.prompt import apply_system_prompt
from agent_eval_lab.runners.worlds import resolve_world
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import LlmJudgeSpec, Task


def run_baseline(
    *,
    dataset_path: Path,
    config: ProviderConfig,
    k: int,
    max_steps: int,
    temperature: float,
    max_tokens: int,
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
                max_tokens=max_tokens,
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


def _write_heartbeat(path: Path, session_id: str) -> None:
    """Operational liveness signal for a stall watchdog: rewritten on every bash
    command so the file's mtime advances continuously during a task. The per-task
    runs JSONL is too coarse — a single hard live task outlives any sane stall
    threshold — so a monitor should watch THIS file (mtime), not the JSONL.
    Content is the live task id, for debuggability. Carries no wall-clock (the
    OS-set mtime is the signal), so it stays out of the deterministic records."""
    path.write_text(session_id, encoding="utf-8")


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


def _parse_runs_spec_with_condition(spec: str) -> tuple[str, str | None, Path]:
    """'LABEL=condition_id=path' or 'LABEL=path' -> (label, condition_id, path).

    report-final makes the middle segment LIVE (grill Q11), unlike
    report-validation's _parse_runs_spec, which discards it. The same
    left-then-right split keeps any interior '=' inside the condition_id.
    """
    label_rest = spec.split("=", 1)
    if len(label_rest) < 2:
        raise ValueError(f"bad --runs spec {spec!r}; want LABEL=condition_id=path")
    label, rest = label_rest
    cond_or_path, *tail = rest.rsplit("=", 1)
    if tail:
        return label, cond_or_path, Path(tail[0])
    return label, None, Path(cond_or_path)


def _derived_condition_id(results: Sequence[RunResult], path: Path) -> str:
    """The condition_id every record in a runs file agrees on (grill Q11)."""
    ids = sorted({run.condition_id for run in results})
    if len(ids) > 1:
        raise ValueError(f"heterogeneous condition_id in {path}: {ids}")
    return ids[0]


def _load_prices(path: Path) -> tuple[str | None, dict[str, TokenPrice]]:
    """prices.json: {"snapshot_date", "prices": {condition_id: {input_per_mtok,
    output_per_mtok}}} — the pinned shape (grill Q11)."""
    data = json.loads(path.read_text())
    prices = {
        condition: TokenPrice(
            input_per_mtok=entry["input_per_mtok"],
            output_per_mtok=entry["output_per_mtok"],
        )
        for condition, entry in data.get("prices", {}).items()
    }
    return data.get("snapshot_date"), prices


def _final_condition_input(spec: str) -> FinalConditionInput:
    label, segment, path = _parse_runs_spec_with_condition(spec)
    results = _load_run_results(path) if path.exists() else []
    derived = _derived_condition_id(results, path) if results else None
    if derived is not None and segment is not None and derived != segment:
        raise ValueError(
            f"--runs {label}: condition_id segment {segment!r} does not match "
            f"the records' {derived!r} in {path}"
        )
    return FinalConditionInput(
        label=label,
        condition_id=derived or segment,
        results=results,
        hosted=_hosted_label(label),
        blocked_reason=None if results else "no reachable records",
    )


def _run_report_final(args: argparse.Namespace) -> int:
    tiers = json.loads(args.tiers.read_text())
    caps = _capability_map(args.dataset)
    snapshot_date, prices = _load_prices(args.prices)
    try:
        conditions = tuple(_final_condition_input(spec) for spec in args.runs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report = build_final_report(
        conditions=conditions,
        dataset_id=args.dataset.stem,
        tiers=tiers,
        capabilities=caps,
        k=args.k,
        expected_n_tasks=args.expected_n_tasks,
        seed=args.seed,
        n_resamples=args.n_resamples,
        alpha=args.alpha,
        prices=prices,
        prices_snapshot_date=snapshot_date,
        context_text=args.context_file.read_text(),
    )
    _atomic_write(args.out, render_final(report))
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
            max_tokens=args.max_tokens,
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


def _spec_from_dict(data: dict) -> ExperimentSpec:
    """Reconstruct an ExperimentSpec from a plain dict (from JSON)."""
    return ExperimentSpec(
        experiment_id=data["experiment_id"],
        k=data["k"],
        repeats=data["repeats"],
        safety_cap=data["safety_cap"],
        max_invalid_rate=data["max_invalid_rate"],
        conditions=tuple(
            ConditionDef(
                condition_id=c["condition_id"],
                label=c["label"],
                skill_variant=c.get("skill_variant", "none"),
                system_prompt_hash=c.get("system_prompt_hash"),
            )
            for c in data["conditions"]
        ),
        metrics=tuple(
            MetricDef(
                name=m["name"],
                domain=m["domain"],
                primary=m["primary"],
                aggregation=m["aggregation"],
                ci_method=m["ci_method"],
                validity_mask=m["validity_mask"],
                censoring_policy=m["censoring_policy"],
            )
            for m in data["metrics"]
        ),
        macro_weights=tuple(
            DomainWeight(domain=w["domain"], weight=w["weight"])
            for w in data["macro_weights"]
        ),
        families=tuple(
            MultiplicityFamily(
                id=f["id"],
                description=f["description"],
                correction=f["correction"],
                alpha=f["alpha"],
            )
            for f in data["families"]
        ),
        planned_comparisons=tuple(
            PlannedComparison(
                name=pc["name"],
                family_id=pc["family_id"],
                domain=pc["domain"],
                condition_a=pc["condition_a"],
                condition_b=pc["condition_b"],
                metric_name=pc["metric_name"],
            )
            for pc in data["planned_comparisons"]
        ),
        dataset_snapshot_hash=data["dataset_snapshot_hash"],
        pricing_snapshot_hash=data["pricing_snapshot_hash"],
        spec_hash=data.get("spec_hash", ""),
    )


def _spec_to_dict(spec: ExperimentSpec) -> dict:
    """Project an ExperimentSpec to a plain JSON-serialisable dict."""
    from agent_eval_lab.experiments.spec_hash import canonical_json as _cj

    # Use canonical_json to serialise then parse back to a plain dict.
    return json.loads(_cj(spec))


def _run_freeze_spec(args: argparse.Namespace) -> int:
    """Load a draft spec JSON, freeze it, write the frozen spec, and print the hash."""
    spec_path = Path(args.spec)
    out_path = Path(args.out)
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[FAIL] spec file not found: {spec_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[FAIL] spec file is not valid JSON: {exc}", file=sys.stderr)
        return 1
    try:
        draft = _spec_from_dict(data)
        frozen = _freeze_spec_pure(draft)
    except (ValueError, TypeError, KeyError) as exc:
        print(f"[FAIL] spec validation error: {exc}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_spec_to_dict(frozen), sort_keys=True, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print(frozen.spec_hash)
    return 0


def _run_check_env(  # noqa: C901
    args: argparse.Namespace, http_client: httpx.Client | None
) -> int:
    """Preflight: verify playwright-cli + MSTR health probe (if config given)."""
    ok = True

    # 1. playwright-cli version check
    try:
        result = subprocess.run(
            ["playwright-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print(f"[ok] playwright-cli: {version}")
        else:
            rc = result.returncode
            print(f"[FAIL] playwright-cli exited {rc}: {result.stderr.strip()}")
            ok = False
    except FileNotFoundError:
        print(
            "[FAIL] playwright-cli not found"
            " — run: npm install -g @playwright/cli@latest"
        )
        ok = False
    except subprocess.TimeoutExpired:
        print("[FAIL] playwright-cli --version timed out")
        ok = False

    # 2. MSTR health probe — only when evaluator config is provided.
    #    Delegates to load_evaluator_config + health_probe so item 006 can
    #    call the same health_probe function directly.
    if args.evaluator_config:
        config_path = Path(args.evaluator_config)
        try:
            cfg = load_evaluator_config(config_path)
            hp = cfg.health_probe
            # The MSTR labs server presents a self-signed cert; TLS verification
            # is disabled for this internal, owner-authorized health probe (the
            # `curl -k` equivalent). Scoped to the probe client only — not a
            # global default. §18.5 needs reachability/auth, not a trusted chain.
            client = http_client or httpx.Client(timeout=10.0, verify=False)
            probe_result = health_probe(
                url=hp.url,
                username=hp.username,
                password=hp.password,
                client=client,
            )
            if probe_result.healthy:
                print(f"[ok] MSTR health probe: HTTP {probe_result.status_code}")
            else:
                print(f"[FAIL] MSTR health probe: HTTP {probe_result.status_code}")
                ok = False
        except FileNotFoundError:
            print(f"[FAIL] evaluator config not found: {config_path}")
            ok = False
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] MSTR health probe error: {exc}")
            ok = False
    else:
        print("[skip] MSTR health probe — pass --evaluator-config to enable")

    return 0 if ok else 1


def _completed_dset_task_ids(path: Path, void_path: Path) -> tuple[set[str], list[str]]:
    """Task ids already finished in a prior (interrupted) run-dset, for resume.

    A task's k_valid records are flushed atomically per task (one yield), so a
    task_id present in the jsonl is fully complete; void task ids (from the sidecar)
    are likewise done. Returns (done_ids, prior_void_ids) so a resumed run skips the
    finished tasks and preserves the prior void sidecar. Pure: reads files only.
    """
    done: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["task_id"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    prior_voids: list[str] = []
    if void_path.exists():
        try:
            payload = json.loads(void_path.read_text(encoding="utf-8"))
            prior_voids = list(payload.get("void_task_ids", []))
        except (json.JSONDecodeError, OSError, AttributeError):
            prior_voids = []
    done.update(prior_voids)
    return done, prior_voids


def _run_dset_command(
    args: argparse.Namespace, http_client: httpx.Client | None
) -> int:
    """EDGE: run a model over the D-set (CMC docs QA) via playwright-cli.

    Resumable: a prior interrupted run's completed tasks (e.g. a network blip aborts
    mid-corpus over a multi-hour run) are skipped and the jsonl is appended to, so a
    transient failure never loses banked tasks — the corpus completes across retries.
    """
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
    from agent_eval_lab.runners.dset_run import run_dset

    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path)
    data = json.loads((store / "cmc-docs-factkeys.json").read_text())
    reference_sha256 = data["snapshot_sha256"]

    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)

    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )

    def health_probe_fn():
        from agent_eval_lab.records.env_health import EnvHealth

        hp = cfg.health_probe
        probe_client = httpx.Client(timeout=10.0, verify=False)
        try:
            r = health_probe(hp.url, hp.username, hp.password, client=probe_client)
        finally:
            probe_client.close()
        return EnvHealth(
            pre_healthy=r.healthy,
            post_healthy=r.healthy,
            pre_status=r.status_code,
            post_status=r.status_code,
        )

    args.out.mkdir(parents=True, exist_ok=True)
    slug = _slug(condition_id(config))
    path = args.out / f"runs-dset-{slug}.jsonl"
    heartbeat_path = path.with_suffix(".heartbeat")

    def heartbeat_fn(session_id: str) -> None:
        _write_heartbeat(heartbeat_path, session_id)

    void_path = path.with_suffix(".void.json")
    done_ids, void_ids = _completed_dset_task_ids(path, void_path)
    remaining = tuple(t for t in tasks if t.id not in done_ids)
    resuming = bool(done_ids)
    if resuming:
        print(
            f"[resume] {len(done_ids)} D-set task(s) already done; "
            f"running {len(remaining)} remaining",
            file=sys.stderr,
        )
    if resuming and not remaining:
        void_path.write_text(json.dumps({"void_task_ids": void_ids}), encoding="utf-8")
        print(path)
        return 0
    aborted = False
    # run_dset yields per task; write each task's runs immediately (flushed) so a
    # later bad request can't lose the tasks already completed. The void sidecar is
    # written in both the clean and the aborted path so report-m1 always finds it.
    try:
        with path.open("a" if resuming else "w") as fh:
            for outcome in run_dset(
                evaluator_store=store,
                tasks=remaining,
                config=config,
                http_client=client,
                k_valid=cfg.runner.k_valid,
                max_invalid_rate=cfg.runner.max_invalid_rate,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                safety_cap=cfg.runner.safety_cap,
                health_probe_fn=health_probe_fn,
                reference_sha256=reference_sha256,
                heartbeat_fn=heartbeat_fn,
            ):
                _append_runs(fh, outcome.valid_runs)
                if outcome.void:
                    tid = outcome.attempts[0].run.task_id if outcome.attempts else "?"
                    void_ids.append(tid)
                    print(
                        f"[void] task {tid}: max invalid-rate tripped with only "
                        f"{len(outcome.valid_runs)} valid trial(s) — condition "
                        f"INCOMPLETE for this task (D34); excluded from pass^k.",
                        file=sys.stderr,
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
        aborted = True
    finally:
        if http_client is None:
            client.close()
    void_path.write_text(json.dumps({"void_task_ids": void_ids}), encoding="utf-8")
    if void_ids:
        print(f"[void] {len(void_ids)} D-set task(s) VOID", file=sys.stderr)
    if aborted:
        return 1
    print(path)
    return 0


def _run_f_command(args: argparse.Namespace, http_client: httpx.Client | None) -> int:
    """EDGE: run ONE arm over the F-domain (web-dossier repo fixes) via the
    candidate-edit loop + held-out node oracle.

    Standalone per-arm (run-dset parity) so F can be run without re-triggering the
    live D-set. env-free: no live infra, no health probe, no VOID. Writes
    runs-m1-<slug>-F.jsonl (+ an empty .void.json) so report-m1 consumes it like
    any other domain artifact."""
    from agent_eval_lab.datasets.f_tasks import build_f_tasks
    from agent_eval_lab.runners.f_candidate import (
        build_candidate_tree,
        make_f_run_fn,
        run_f_candidate,
    )

    # Fail fast on an incapable node BEFORE any paid call: the held-out oracle
    # needs Node >=20 (`--test-reporter=junit`); otherwise every attempt grades
    # FAIL silently (the node-v16 incident). Set NODE_BIN to a Node >=20 binary.
    if http_client is None and not node_supports_junit():
        print(
            "error: resolved node cannot run the held-out oracle "
            "(needs `--test-reporter=junit`, Node >=20). Set NODE_BIN to a "
            "Node >=20 binary and retry.",
            file=sys.stderr,
        )
        return 1

    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path)

    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)
    cond = condition_id(config)

    tasks = build_f_tasks(evaluator_store=store / "web-dossier-golden")
    f_repo = Path.home() / "Documents/Repository/web-dossier"
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )

    from agent_eval_lab.runners.round_budget import DOMAIN_MAX_ROUNDS

    run_fn = make_f_run_fn(
        config=config,
        http_client=client,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        condition_id=cond,
        safety_cap=cfg.runner.safety_cap,
        # F is arm-wide in this phase; per-task F overrides arrive in item 003.
        max_rounds=DOMAIN_MAX_ROUNDS["F"],
    )

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"runs-m1-{_slug(cond)}-F.jsonl"
    void_ids: list[str] = []
    aborted = False
    try:
        with path.open("w") as fh:
            for outcome in run_f_candidate(
                tasks=tasks,
                k=cfg.runner.k_valid,
                condition_id=cond,
                build_tree_fn=lambda task: build_candidate_tree(task, repo=f_repo),
                run_fn=run_fn,
            ):
                _append_runs(fh, outcome.valid_runs)
                if outcome.void:
                    tid = outcome.attempts[0].run.task_id if outcome.attempts else "?"
                    void_ids.append(tid)
                    print(
                        f"[void] F task {tid}: fewer than k clean trials — provider "
                        "errors masked (env-invalid); excluded from pass^k (D34).",
                        file=sys.stderr,
                    )
    except httpx.TransportError as exc:
        hint = " — is the server running?" if config.id == "local" else ""
        print(
            f"error: cannot reach provider {config.id!r} at {config.base_url} "
            f"({type(exc).__name__}: {exc}){hint}",
            file=sys.stderr,
        )
        aborted = True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"error: git command failed building candidate tree: {exc}",
            file=sys.stderr,
        )
        aborted = True
    finally:
        if http_client is None:
            client.close()
        # Write the void sidecar unconditionally so report-m1 can find it even when
        # the run aborts mid-corpus (transport failure or missing repo).
        path.with_suffix(".void.json").write_text(
            json.dumps({"void_task_ids": void_ids}), encoding="utf-8"
        )
    if aborted:
        return 1
    print(path)
    return 0


def _load_m1_domain_tasks(args, cfg) -> dict:
    """Build the per-domain task map.
    D = CMC docs tasks; F = web-dossier repo-fix tasks (009); B = MSTR readback
    B-1 (010), present only when the gitignored b-set golden store + stripped
    skill fork are on disk (B-1 is a 1-task contingency — D26).
    cfg is the loaded EvaluatorConfig (passed so callers can stub this function
    in tests without touching load_evaluator_config)."""
    from agent_eval_lab.datasets.b_tasks import build_b_tasks
    from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
    from agent_eval_lab.datasets.f_tasks import build_f_tasks

    store = Path(cfg.store.path)
    tasks = build_cmc_tasks(
        evaluator_store=store,
        questions_path=Path("examples/datasets/cmc-docs-questions.txt"),
    )
    f_tasks = build_f_tasks(evaluator_store=store / "web-dossier-golden")
    domain_tasks: dict = {"D": tasks, "F": f_tasks}

    # B is gated on the gitignored golden store + the stripped skill fork. When
    # either is absent (CI / no evaluator-only), B is simply omitted (mirrors the
    # absent-domain skip in run_m1). B-1 is a 1-task contingency (D26).
    golden_dir = Path("evaluator-only/b-set-golden")
    skill_cfg = getattr(cfg, "skill", None)
    skill_path = Path(skill_cfg.strategy_test_path) if skill_cfg is not None else None
    if (
        skill_path is not None
        and (golden_dir / "b1-golden.json").exists()
        and skill_path.exists()
    ):
        domain_tasks["B"] = build_b_tasks(
            golden_dir=golden_dir, strategy_test_path=skill_path
        )
    return domain_tasks


def _run_m1_command(args: argparse.Namespace, http_client: httpx.Client | None) -> int:
    data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec = _spec_from_dict(data)
    if not spec.spec_hash:
        print("error: spec is not frozen (run freeze-spec first)", file=sys.stderr)
        return 1

    # Load evaluator config; allow tests to monkeypatch _load_m1_domain_tasks
    # so that a missing evaluator.toml is never reached in unit tests.
    evaluator_config_path = Path(args.evaluator_config)
    try:
        cfg = load_evaluator_config(evaluator_config_path)
    except FileNotFoundError:
        print(
            f"error: evaluator config not found: {evaluator_config_path}",
            file=sys.stderr,
        )
        return 1

    store = Path(cfg.store.path)
    reference_sha256 = None
    factkeys = store / "cmc-docs-factkeys.json"
    if factkeys.exists():
        reference_sha256 = json.loads(factkeys.read_text())["snapshot_sha256"]

    providers = args.provider or sorted(PROVIDERS)
    configs = tuple(PROVIDERS[p] for p in providers)
    domain_tasks = _load_m1_domain_tasks(args, cfg)

    if domain_tasks.get("B"):
        print(
            "note: B-domain tasks loaded but skipped — live MSTR readback client not "
            "wired (deferred; see EXECUTE-DEFERRED.md)",
            file=sys.stderr,
        )

    client = http_client or httpx.Client(timeout=120.0, trust_env=False)

    def health_probe_fn():
        from agent_eval_lab.records.env_health import EnvHealth

        hp = cfg.health_probe
        probe_client = httpx.Client(timeout=10.0, verify=False)
        try:
            r = health_probe(hp.url, hp.username, hp.password, client=probe_client)
        finally:
            probe_client.close()
        return EnvHealth(
            pre_healthy=r.healthy,
            post_healthy=r.healthy,
            pre_status=r.status_code,
            post_status=r.status_code,
        )

    try:
        outcomes = run_m1(
            configs=configs,
            domain_tasks=domain_tasks,
            http_client=client,
            k_valid=cfg.runner.k_valid,
            max_invalid_rate=cfg.runner.max_invalid_rate,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            health_probe_fn=health_probe_fn,
            reference_sha256=reference_sha256,
            evaluator_store=store,
            f_repo=Path.home() / "Documents/Repository/web-dossier",
            # DEFERRED: live playwright-cli readback client (EXECUTE-DEFERRED)
            b_client=None,
            b_project_id=cfg.oracle_b_set.project_id,
            b_folder="/runs",
        )
    finally:
        if http_client is None:
            client.close()

    args.out.mkdir(parents=True, exist_ok=True)
    for cond, by_domain in outcomes.items():
        for domain, domain_outcomes in by_domain.items():
            path = args.out / f"runs-m1-{_slug(cond)}-{domain}.jsonl"
            void_ids: list[str] = []
            with path.open("w") as fh:
                for o in domain_outcomes:
                    _append_runs(fh, o.valid_runs)
                    if o.void:
                        tid = o.attempts[0].run.task_id if o.attempts else "?"
                        void_ids.append(tid)
                        print(
                            f"[void] {cond}/{domain} task {tid}: INCOMPLETE (D34)",
                            file=sys.stderr,
                        )
            # Persist void/INCOMPLETE task ids beside the runs: the valid-runs-only
            # JSONL can't convey them, so report-m1's replay would under-count voids
            # without this sidecar (L2).
            path.with_suffix(".void.json").write_text(
                json.dumps({"void_task_ids": void_ids}), encoding="utf-8"
            )
            print(path)
    return 0


def _parse_domain_runs_spec(spec: str) -> tuple[str, str, Path]:
    """'DOMAIN:condition_id=path' -> (domain, condition_id, path). condition_id
    may contain '=' (openrouter-style), so split domain off the left then path
    off the right."""
    if ":" not in spec:
        raise ValueError(f"bad --runs spec {spec!r}; want DOMAIN:condition_id=path")
    domain, rest = spec.split(":", 1)
    cond, *tail = rest.rsplit("=", 1)
    if not tail:
        raise ValueError(f"bad --runs spec {spec!r}; missing '=path'")
    return domain, cond, Path(tail[0])


def _outcomes_from_runs(
    results: Sequence[RunResult],
    void_task_ids: frozenset[str] = frozenset(),
    *,
    k: int | None = None,
) -> tuple[ReplacementOutcome, ...]:
    """One ReplacementOutcome per task_id. The run path writes only valid runs;
    a task listed in the run's `.void.json` sidecar is marked void=True (D34
    INCOMPLETE) with whatever partial valid runs it produced — including the
    zero-valid case (a fully-void task has no JSONL rows but is restored from the
    sidecar). Without a sidecar (legacy artifacts) every task is non-void (L2).

    Env-validity mask: a PROVIDER-side failure (`is_env_invalid_run` — a rejected
    /chat/completions or empty choices) is masked out of `valid_runs` and flagged
    invalid in `attempts`, never scored as a model failure. When `k` is given, a
    task that could not obtain `k` clean trials is INCOMPLETE -> void (never scored
    over <k, D34) — this is the F-domain analogue of the D-set health-probe mask
    for the env-free run path, which has no live probe."""
    by_task: dict[str, list[RunResult]] = {}
    for r in results:
        by_task.setdefault(r.task_id, []).append(r)
    outcomes = []
    for tid in sorted(set(by_task) | set(void_task_ids)):
        runs = tuple(by_task.get(tid, ()))
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=not is_env_invalid_run(r), run=r)
            for i, r in enumerate(runs)
        )
        valid_runs = tuple(r for r in runs if not is_env_invalid_run(r))
        under_powered = bool(runs) and k is not None and len(valid_runs) < k
        outcomes.append(
            ReplacementOutcome(
                valid_runs=valid_runs,
                attempts=attempts,
                void=(tid in void_task_ids) or under_powered,
            )
        )
    return tuple(outcomes)


def _void_task_ids_for(path: Path) -> frozenset[str]:
    """Read the `<runs>.void.json` sidecar (written by run-m1) if present."""
    sidecar = path.with_suffix(".void.json")
    if not sidecar.exists():
        return frozenset()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    return frozenset(data.get("void_task_ids", ()))


def _run_report_m1(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec = _spec_from_dict(data)
    if not spec.spec_hash:
        print("error: spec is not frozen (run freeze-spec first)", file=sys.stderr)
        return 1
    pricing = load_pricing(args.prices)
    outcomes: dict[str, dict[str, tuple[ReplacementOutcome, ...]]] = {}
    for spec_str in args.runs:
        try:
            domain, cond, path = _parse_domain_runs_spec(spec_str)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        results = _load_run_results(path) if path.exists() else []
        outcomes.setdefault(cond, {})[domain] = _outcomes_from_runs(
            results, _void_task_ids_for(path), k=spec.k
        )
    report = build_m1_report(
        spec=spec,
        outcomes_by_condition_domain=outcomes,
        pricing=pricing,
        seed=args.seed,
        n_resamples=args.n_resamples,
        alpha=args.alpha,
    )
    _atomic_write(args.out, render_m1(report))
    print(args.out)
    if args.subreports:
        out_dir = args.subreport_dir or args.out.parent
        for domain in report.subreport_domains:
            outcomes_for_domain = {
                cond: outcomes[cond][domain]
                for cond in sorted(outcomes)
                if domain in outcomes[cond]
            }
            detail = build_m1_detail(
                domain=domain,
                outcomes_by_condition=outcomes_for_domain,
                pricing=pricing,
                spec=spec,
            )
            subreport_path = out_dir / f"M1-{domain}-report.md"
            _atomic_write(subreport_path, render_detail(detail))
            print(subreport_path)
    return 0


def _ablation_arm_tasks(store: Path) -> dict[str, Task]:
    """The 12 F task-arms indexed by task_id (the arm rides task_id, §B.2)."""
    from agent_eval_lab.datasets.f_tasks import build_f_task_arms

    return {t.id: t for t in build_f_task_arms(evaluator_store=store)}


def _default_run_fn_factory(
    *, http_client: httpx.Client | None, temperature: float, max_tokens: int
):
    """Production factory: per condition_id, build the REAL make_f_run_fn driver.
    Called ONLY on a non-dry user invocation — this is the sole provider-call path
    (V arms route through the 005 sandbox on macOS via make_f_run_fn). Tests inject
    a fake factory instead, so no test/CI path ever reaches a network client."""

    def factory(*, condition_id: str, safety_cap: int):
        provider = condition_id.split(":", 1)[0]
        config = PROVIDERS[provider]
        model = condition_id.split(":", 1)[1]
        config = replace(config, model_id=model)
        client = http_client or httpx.Client(
            timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
        )
        return make_f_run_fn(
            config=config,
            http_client=client,
            temperature=temperature,
            max_tokens=max_tokens,
            condition_id=condition_id,
            safety_cap=safety_cap,
            max_rounds=40,  # the frozen uniform ablation cap (§B.1)
        )

    return factory


def _write_realized_order(
    out: Path, order: Sequence[RunUnit], *, experiment_id: str, spec_hash: str
) -> None:
    """Persist the realized execution / API-call order for audit (§10.7). Pure
    projection of RunUnits to plain dicts; the on-disk record order in the JSONL is
    NOT this — this sidecar is the authoritative drift-control record. It also
    records experiment_id + spec_hash so a run is reconstructable from artifacts
    even though the roster now lives in config rather than frozen source."""
    payload = {
        "experiment_id": experiment_id,
        "spec_hash": spec_hash,
        "seed": ABLATION_SEED,
        "realized_order": [
            {
                "model": u.model,
                "task_id": u.task_id,
                "base_task": u.base_task,
                "arm": u.arm,
                "repetition": u.repetition,
            }
            for u in order
        ],
    }
    _atomic_write(
        out / "f-ablation.realized-order.json",
        json.dumps(payload, indent=2, sort_keys=True),
    )


def _run_f_ablation_command(  # noqa: C901
    args: argparse.Namespace,
    http_client: httpx.Client | None,
    *,
    run_fn_factory=None,
) -> int:
    """EDGE: orchestrate the F-set ablation in the FROZEN seeded ablation_run_order
    across (model × task-arm × rep). The arm rides each run's task_id (§B.2). Writes
    one artifact per condition (runs-ablation-{slug}-F.jsonl, all 12 task-arms
    inside) + a realized-order sidecar (the API-call order controls drift, not the
    on-disk record order — §10.7).

    Provider calls happen ONLY when the user invokes this WITHOUT --dry-run and with
    no injected run_fn_factory. --dry-run writes the realized order and makes ZERO
    run_fn calls (a network-free preview + the unit-test seam).

    The roster (WHICH models compete) is read from args.roster (the committed
    f-ablation-roster.toml by default) — add/remove a model there, no code change.
    A typo'd provider is rejected at load, before any paid call."""
    roster = load_f_ablation_roster(args.roster, valid_providers=frozenset(PROVIDERS))
    spec = _freeze_spec_pure(
        build_f_ablation_spec(
            conditions=roster.conditions,
            experiment_id=roster.experiment_id,
            dataset_snapshot_hash="",
            pricing_snapshot_hash="",
        )
    )
    models = tuple(c.condition_id for c in spec.conditions)
    base_tasks = ("f1", "f2", "f3")
    order = ablation_run_order(
        seed=ABLATION_SEED, models=models, base_tasks=base_tasks, k=spec.k
    )
    # Optional arm filter (e.g. re-run ONLY the V arms after a contaminated run).
    # Applied to the FULL seeded order so each kept unit retains its original
    # relative position — selecting a subset never reshuffles the survivors.
    selected_arms = getattr(args, "arms", None)
    if selected_arms:
        order = tuple(u for u in order if u.arm in selected_arms)

    args.out.mkdir(parents=True, exist_ok=True)
    realized: list[RunUnit] = []

    if args.dry_run:
        # Preview ONLY: record the realized order, make NO run_fn call (no network).
        _write_realized_order(
            args.out,
            order,
            experiment_id=spec.experiment_id,
            spec_hash=spec.spec_hash,
        )
        print(args.out / "f-ablation.realized-order.json")
        return 0

    # Fail fast: the held-out node oracle grades EVERY arm via
    # `node --test --test-reporter=junit` (Node >=20). If the resolvable node
    # can't run it, every attempt would silently grade FAIL (the node-v16
    # incident) — refuse before any paid call. The injected-factory test seam
    # (run_fn_factory is not None) is exempt: its grading is over stub trees.
    if run_fn_factory is None and not node_supports_junit():
        print(
            "error: resolved node cannot run the held-out oracle "
            "(needs `--test-reporter=junit`, Node >=20). Set NODE_BIN to a "
            "Node >=20 binary and retry — refusing so attempts are not all "
            "graded FAIL by an incapable node.",
            file=sys.stderr,
        )
        return 1

    f_repo = Path.home() / "Documents/Repository/web-dossier"
    if run_fn_factory is not None:
        # Injected factory (test path): skip config I/O; use a sentinel store.
        arm_tasks = _ablation_arm_tasks(Path("/nonexistent"))
        factory = run_fn_factory
        safety_cap = 200  # spec default; irrelevant on the test path
    else:
        cfg = load_evaluator_config(args.evaluator_config)
        store = Path(cfg.store.path) / "web-dossier-golden"
        arm_tasks = _ablation_arm_tasks(store)
        factory = _default_run_fn_factory(
            http_client=http_client,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        safety_cap = cfg.runner.safety_cap

    # Validate task_id coverage BEFORE any provider call (catch skew early). Every
    # task_id the (possibly arm-filtered) order references MUST exist in arm_tasks;
    # arm_tasks may legitimately carry MORE ids than a filtered order touches.
    expected_ids = {u.task_id for u in order}
    actual_ids = set(arm_tasks)
    missing = expected_ids - actual_ids
    if missing:
        print(
            f"error: task_id skew — order references ids not in arm_tasks: "
            f"missing={sorted(missing)!r}",
            file=sys.stderr,
        )
        return 1

    # Open one JSONL file handle per condition BEFORE the loop (stream, don't buffer).
    handles: dict[str, TextIO] = {}
    run_fns: dict[str, object] = {}
    aborted = False
    try:
        for cond in models:
            path = args.out / f"runs-ablation-{_slug(cond)}-F.jsonl"
            handles[cond] = path.open("w")

        for unit in order:
            run_fn = run_fns.get(unit.model)
            if run_fn is None:
                run_fn = factory(condition_id=unit.model, safety_cap=safety_cap)
                run_fns[unit.model] = run_fn
            task = arm_tasks[unit.task_id]
            base_tree = build_candidate_tree(task, repo=f_repo)
            edit_task = make_edit_task(task, base_tree=base_tree)
            traj = run_fn(edit_task, unit.repetition)
            result = grade_f_attempt(
                task, traj, condition_id=unit.model, run_index=unit.repetition
            )
            _append_runs(handles[unit.model], [result])
            realized.append(unit)
    except httpx.TransportError as exc:
        print(
            f"error: cannot reach provider ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        aborted = True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"error: git command failed building candidate tree: {exc}",
            file=sys.stderr,
        )
        aborted = True
    finally:
        for fh in handles.values():
            fh.close()
        # Write the realized-order sidecar of whatever was executed so far.
        # A partial/aborted run still leaves completed JSONL rows + a sidecar.
        _write_realized_order(
            args.out,
            tuple(realized),
            experiment_id=spec.experiment_id,
            spec_hash=spec.spec_hash,
        )

    if aborted:
        return 1
    print(args.out)
    return 0


def _real_claude_factory():
    import subprocess as _sp
    import tempfile

    def factory(*, model, surface):
        def run_subprocess(argv, *, cwd, env, timeout):
            return _sp.run(
                argv,
                cwd=cwd,
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True,
            )

        def workdir_factory():
            return (
                Path(tempfile.mkdtemp(prefix="claude-f-")),
                Path(tempfile.mkdtemp(prefix="claude-home-")),
            )

        return make_claude_run_fn(
            model=model,
            surface=surface,
            run_subprocess=run_subprocess,
            workdir_factory=workdir_factory,
        )

    return factory


def _run_f_claude_baseline_command(args, *, run_fn_factory=None) -> int:
    surfaces = (
        ["edit-only"]
        if args.smoke
        else ["edit-only", "natural"]
        if args.surface == "both"
        else [args.surface]
    )
    bases = ["f1"] if args.smoke else list(args.bases)
    k = 1 if args.smoke else args.k

    args.out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        plan = {
            "surfaces": surfaces,
            "bases": bases,
            "k": k,
            "attempts": len(surfaces) * len(bases) * k,
        }
        (args.out / "claude-baseline.plan.json").write_text(json.dumps(plan, indent=2))
        print(args.out / "claude-baseline.plan.json")
        return 0

    # Fail fast: the held-out oracle needs Node >=20 (cf. _run_f_ablation_command).
    if run_fn_factory is None and not node_supports_junit():
        print(
            "error: resolved node cannot run the held-out oracle (needs Node >=20). "
            "Set NODE_BIN to a Node >=20 binary and retry.",
            file=sys.stderr,
        )
        return 1

    f_repo = Path.home() / "Documents/Repository/web-dossier"
    # Fail fast on a missing F repo (real runs only; injected-factory tests skip).
    if run_fn_factory is None and not f_repo.exists():
        print(
            f"error: F repo not found at {f_repo}. Clone web-dossier there and retry.",
            file=sys.stderr,
        )
        return 1
    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path) / "web-dossier-golden"
    all_tasks = {t.id: t for t in build_f_tasks(evaluator_store=store)}
    base_to_task = {b: all_tasks[f"f-{b}"] for b in bases}

    factory = run_fn_factory or _real_claude_factory()
    rows: list[BaselineRow] = []
    handles: dict[str, TextIO] = {}
    try:
        for surface in surfaces:
            cond = f"claude-cli:{args.model}:{surface}"
            handle = (args.out / f"runs-claude-{_slug(cond)}-F.jsonl").open("w")
            handles[cond] = handle
            run_fn = factory(model=args.model, surface=surface)
            outcomes = list(
                run_f_candidate(
                    tasks=[base_to_task[b] for b in bases],
                    k=k,
                    condition_id=cond,
                    build_tree_fn=lambda t: build_candidate_tree(t, repo=f_repo),
                    run_fn=run_fn,
                )
            )
            for outcome in outcomes:
                _append_runs(handle, [att.run for att in outcome.attempts])
            rows.extend(summarize_baseline(cond, bases, outcomes))
    finally:
        for fh in handles.values():
            fh.close()

    (args.out / "claude-baseline-summary.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2)
    )
    print(args.out / "claude-baseline-summary.json")
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
    baseline.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Explicit completion budget sent in every chat_completion request "
        "(never a provider default); default 4096. The trajectory records this "
        "value so the fc-v2 classifier can distinguish token_budget_exhausted "
        "from malformed_reply without re-parsing CLI arguments (ADR-0013).",
    )
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

    rf = subparsers.add_parser(
        "report-final",
        help="rebuild the final evaluation report from JSONL (pure, replay-only)",
    )
    rf.add_argument(
        "--runs",
        required=True,
        nargs="+",
        help="one per condition: LABEL=condition_id=path/to/runs-*.jsonl "
        "(the condition_id segment is cross-checked against the records)",
    )
    rf.add_argument("--dataset", required=True, type=Path)
    rf.add_argument("--tiers", required=True, type=Path)
    rf.add_argument("--prices", required=True, type=Path)
    rf.add_argument("--context-file", required=True, type=Path)
    rf.add_argument("--k", type=int, default=3)
    rf.add_argument("--expected-n-tasks", type=int, default=15)
    rf.add_argument("--out", required=True, type=Path)
    rf.add_argument("--seed", type=int, default=20260610)
    rf.add_argument("--n-resamples", type=int, default=2000)
    rf.add_argument("--alpha", type=float, default=0.05)

    ce = subparsers.add_parser(
        "check-env",
        help="preflight: verify playwright-cli + MSTR environment health",
    )
    ce.add_argument(
        "--evaluator-config",
        type=Path,
        metavar="TOML",
        help="path to evaluator.toml (enables MSTR health probe)",
    )

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

    fs = subparsers.add_parser(
        "freeze-spec",
        help="validate and freeze an ExperimentSpec JSON, writing the spec_hash",
    )
    fs.add_argument(
        "--spec", required=True, metavar="DRAFT_JSON", help="path to draft spec JSON"
    )
    fs.add_argument(
        "--out", required=True, metavar="FROZEN_JSON", help="path for frozen output"
    )

    rd = subparsers.add_parser(
        "run-dset", help="run a model over the D-set (CMC docs) via playwright-cli"
    )
    rd.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    rd.add_argument("--model", help="override the provider's default model id")
    rd.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rd.add_argument("--out", type=Path, default=Path("reports"))
    rd.add_argument("--temperature", type=float, default=0.0)
    rd.add_argument("--max-tokens", type=int, default=4096)

    rf2 = subparsers.add_parser(
        "run-f",
        help="run one arm over the F-domain (web-dossier repo fixes) — env-free",
    )
    rf2.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    rf2.add_argument("--model", help="override the provider's default model id")
    rf2.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rf2.add_argument("--out", type=Path, default=Path("reports"))
    rf2.add_argument("--temperature", type=float, default=0.0)
    rf2.add_argument("--max-tokens", type=int, default=16384)

    rfa = subparsers.add_parser(
        "run-f-ablation",
        help="orchestrate the F-set 2×2 ablation in the frozen seeded order "
        "(one artifact per condition + realized-order sidecar). --dry-run previews "
        "the order with NO provider calls.",
    )
    rfa.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rfa.add_argument(
        "--roster",
        type=Path,
        default=Path("f-ablation-roster.toml"),
        metavar="TOML",
        help="roster of models to compare (provider:model + label per [[model]]); "
        "edit this to add/remove a model — no code change. Default: "
        "f-ablation-roster.toml at repo root.",
    )
    rfa.add_argument("--out", type=Path, default=Path("reports"))
    rfa.add_argument("--temperature", type=float, default=0.0)
    rfa.add_argument("--max-tokens", type=int, default=16384)
    rfa.add_argument(
        "--arms",
        nargs="+",
        choices=list(ARMS),
        default=None,
        metavar="ARM",
        help="restrict the run to these 2×2 arms (default: all four). Applied to "
        "the full seeded order, so survivors keep their relative position — used "
        "to re-run only a subset (e.g. `--arms feedback both`).",
    )
    rfa.add_argument(
        "--dry-run",
        action="store_true",
        help="write the realized run order and exit WITHOUT any provider call "
        "(network-free preview / audit).",
    )

    cb = subparsers.add_parser(
        "run-f-claude-baseline",
        help="run vanilla claude -p (Sonnet 4.6, no skills) as the F-task agent",
    )
    cb.add_argument("--out", type=Path, required=True)
    cb.add_argument(
        "--surface", choices=["edit-only", "natural", "both"], default="both"
    )
    cb.add_argument("--k", type=int, default=5)
    cb.add_argument(
        "--bases", nargs="+", choices=["f1", "f2", "f3"], default=["f1", "f2", "f3"]
    )
    cb.add_argument("--model", default="claude-sonnet-4-6")
    cb.add_argument("--evaluator-config", type=Path, default=Path("evaluator.toml"))
    cb.add_argument(
        "--smoke",
        action="store_true",
        help="1 attempt, base f1, edit-only — validate plumbing/cost, then stop",
    )
    cb.add_argument("--dry-run", action="store_true")

    rmm = subparsers.add_parser(
        "run-m1", help="orchestrate M1 conditions × domains over the runners"
    )
    rmm.add_argument(
        "--spec", required=True, type=Path, help="frozen ExperimentSpec JSON"
    )
    rmm.add_argument(
        "--provider",
        action="append",
        choices=sorted(PROVIDERS),
        help="repeatable; default = all reachable providers",
    )
    rmm.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rmm.add_argument("--out", type=Path, default=Path("reports"))
    rmm.add_argument("--temperature", type=float, default=0.0)
    rmm.add_argument("--max-tokens", type=int, default=4096)

    rm = subparsers.add_parser(
        "report-m1",
        help="aggregate recorded M1 runs into the per-domain + macro report (pure)",
    )
    rm.add_argument(
        "--spec", required=True, type=Path, help="frozen ExperimentSpec JSON"
    )
    rm.add_argument(
        "--runs",
        required=True,
        nargs="+",
        help="one per (domain,condition): DOMAIN:condition_id=path/to/runs.jsonl",
    )
    rm.add_argument("--prices", required=True, type=Path)
    rm.add_argument("--out", required=True, type=Path)
    rm.add_argument("--seed", type=int, default=20260613)
    rm.add_argument("--n-resamples", type=int, default=2000)
    rm.add_argument("--alpha", type=float, default=0.05)
    rm.add_argument(
        "--subreports",
        dest="subreports",
        action="store_true",
        default=True,
        help="also write per-domain M1-<domain>-report.md subreports (default on)",
    )
    rm.add_argument(
        "--no-subreports",
        dest="subreports",
        action="store_false",
        help="suppress per-domain subreports",
    )
    rm.add_argument(
        "--subreport-dir",
        type=Path,
        default=None,
        help="directory for subreports (default: same dir as --out)",
    )

    return parser


def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "freeze-spec":
        return _run_freeze_spec(args)
    if args.command == "check-env":
        return _run_check_env(args, http_client)
    if args.command == "calibrate":
        return _run_calibrate(args, parser, http_client)
    if args.command == "report-validation":
        return _run_report_validation(args)
    if args.command == "report-final":
        return _run_report_final(args)
    if args.command == "compare-configs":
        return _run_compare_configs(args)
    if args.command == "run-dset":
        return _run_dset_command(args, http_client)
    if args.command == "run-f":
        return _run_f_command(args, http_client)
    if args.command == "run-f-ablation":
        return _run_f_ablation_command(args, http_client)
    if args.command == "run-f-claude-baseline":
        return _run_f_claude_baseline_command(args)
    if args.command == "report-m1":
        return _run_report_m1(args)
    if args.command == "run-m1":
        return _run_m1_command(args, http_client)
    return _run_baseline_command(args, parser, http_client)


if __name__ == "__main__":
    raise SystemExit(main())
