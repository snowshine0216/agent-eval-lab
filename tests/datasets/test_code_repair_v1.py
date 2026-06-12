"""code_repair_v1 conformance: every quality claim is proven mechanically.

Runs the production oracle edge on real sandboxed pytest (ADR-0010/0011/0012):
shape/metadata/tier/capability/knob contracts, world validity over all four
fixture-tree kinds, oracle-path disjointness, symptom reality, solvability,
no-op zero, stub neutralization, hack breadth, anti-rote and oracle-leakage
proxies, policy coherence, distractor integrity, ledger parity, determinism.
"""

import json
import re
from collections import Counter
from collections.abc import Mapping
from functools import cache, lru_cache
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    collect_execution_specs,
    execution_hash,
)
from agent_eval_lab.records.serialize import grade_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.runners.pytest_edge import run_pytest
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    Task,
    TrajectorySpec,
)
from agent_eval_lab.tools.code_world import (
    CODE_WORLD_TOOLS,
    path_error,
    prefix_collision,
)

_REPO = Path(__file__).parent.parent.parent
DATASET = _REPO / "examples/datasets/code_repair_v1.jsonl"
TIERS_SIDECAR = _REPO / "examples/datasets/code_repair_v1_tiers.json"
FIXTURES_SIDECAR = _REPO / "examples/datasets/code_repair_v1_review_fixtures.json"
LEDGER = _REPO / "docs/2026-06-11-coding-agent-eval/review-ledger.md"

_CAPABILITIES = {
    "visible_test_localization",
    "prose_localization",
    "test_comprehension",
    "cross_file_repair",
    "regression_preservation",
    "overfit_resistance",
}
_KNOBS = {
    "fault_distance",
    "multi_hunk",
    "oracle_breadth",
    "spec_obliqueness",
    "constraint_budget",
    "distractor_file",
}
_BUG_CLASSES = {
    "off_by_one",
    "logic_inversion",
    "exception_handling",
    "type_coercion",
    "boundary_condition",
    "aliasing_mutation",
}
_BANNED_IMPORTS = {
    "socket",
    "http",
    "urllib",
    "requests",
    "subprocess",
    "multiprocessing",
    "threading",
    "asyncio",
    "random",
    "secrets",
    "uuid",
    "time",
    "datetime",
    "os",
    "tempfile",
}
_RESERVED_BASENAMES = {
    ".harness.ini",
    ".junit.xml",
    "sitecustomize.py",
    "usercustomize.py",
    "conftest.py",
}
_CODE_TOOLS = {"read_file", "write_file", "list_files", "run_tests"}
_TIER_ALLOCATION = {"T1": 2, "T2": 4, "T3": 6, "T4": 3}
_STUB = "def test_stub():\n    pass\n"


# ---- pure loaders and walkers -----------------------------------------------


@lru_cache(maxsize=1)
def _tasks() -> tuple[Task, ...]:
    return load_tasks(DATASET)


def _task(task_id: str) -> Task:
    return next(t for t in _tasks() if t.id == task_id)


@lru_cache(maxsize=1)
def _tiers() -> dict[str, str]:
    return json.loads(TIERS_SIDECAR.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _fixtures() -> dict[str, dict]:
    return json.loads(FIXTURES_SIDECAR.read_text(encoding="utf-8"))


def _initial_files(task: Task) -> dict[str, str]:
    return dict((task.initial_state or {}).get("files", {}))


def _oracle_spec(task: Task) -> ExecutionSpec:
    specs = collect_execution_specs(task.verification)
    assert len(specs) == 1, f"{task.id}: expected exactly one ExecutionSpec"
    return specs[0]


def _trajectory_specs(task: Task) -> tuple[TrajectorySpec, ...]:
    def walk(spec) -> tuple[TrajectorySpec, ...]:
        if isinstance(spec, TrajectorySpec):
            return (spec,)
        if isinstance(spec, AllOf):
            return tuple(t for sub in spec.specs for t in walk(sub))
        return ()

    return walk(task.verification)


def _basename(path: str) -> str:
    return path.split("/")[-1]


def _is_test_basename(path: str) -> bool:
    name = _basename(path)
    return name.startswith("test_") and name.endswith(".py")


def _visible_test_paths(task: Task) -> tuple[str, ...]:
    return tuple(p for p in sorted(_initial_files(task)) if _is_test_basename(p))


def _solution(task: Task) -> dict[str, str]:
    return dict(_fixtures()[task.id]["solution"])


def _hack(task: Task) -> dict[str, str] | None:
    raw = _fixtures()[task.id]["hack"]
    return None if raw is None else dict(raw)


def _fixture_trees(task: Task) -> dict[str, Mapping[str, str]]:
    """The four fixture-tree kinds this item ships (hack may be absent)."""
    trees: dict[str, Mapping[str, str]] = {
        "initial": _initial_files(task),
        "oracle": dict(_oracle_spec(task).held_out_tests),
        "solution": _solution(task),
    }
    hack = _hack(task)
    if hack is not None:
        trees["hack"] = hack
    return trees


def _imported_roots(content: str) -> set[str]:
    """Top-level module names named by import statements (mechanical scan)."""
    roots: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            for part in stripped[len("import ") :].split(","):
                roots.add(part.strip().split(" ")[0].split(".")[0])
        elif stripped.startswith("from "):
            roots.add(stripped.split()[1].split(".")[0])
    return roots


def _prompt_text(task: Task) -> str:
    return "\n".join(m.content for m in task.input.messages)


def _nontrivial_lines(content: str) -> set[str]:
    return {line.strip() for line in content.splitlines() if len(line.strip()) > 3}


# ---- synthetic trajectories + cached sandbox runs ---------------------------


def _trajectory(final_state: Mapping) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="Done."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _grade(task: Task, final_files: Mapping[str, str]):
    """Production path: oracle edge precompute, then the pure graders."""
    trajectory = _trajectory({"files": dict(final_files)})
    verdicts = precompute_execution_verdicts(
        verification=task.verification, trajectory=trajectory
    )
    grade = grade_trajectory(
        verification=task.verification,
        trajectory=trajectory,
        registry=CODE_WORLD_TOOLS,
        initial_state=task.initial_state,
        verdicts=verdicts,
    )
    key = execution_hash(_oracle_spec(task), dict(final_files))
    return grade, verdicts.get(key)


@cache
def _initial_run(task_id: str):
    return run_pytest(_initial_files(_task(task_id)))


@cache
def _reference_files(task_id: str) -> tuple[tuple[str, str], ...]:
    task = _task(task_id)
    return tuple(sorted({**_initial_files(task), **_solution(task)}.items()))


@cache
def _reference_visible_run(task_id: str):
    return run_pytest(dict(_reference_files(task_id)))


@cache
def _reference_grade(task_id: str):
    return _grade(_task(task_id), dict(_reference_files(task_id)))


@cache
def _noop_grade(task_id: str):
    task = _task(task_id)
    return _grade(task, _initial_files(task))


@cache
def _stub_grade(task_id: str):
    task = _task(task_id)
    stubbed = {
        **_initial_files(task),
        **{p: _STUB for p in _visible_test_paths(task)},
    }
    return _grade(task, stubbed)


@cache
def _hack_files(task_id: str) -> tuple[tuple[str, str], ...]:
    task = _task(task_id)
    hack = _hack(task)
    assert hack is not None
    return tuple(sorted({**_initial_files(task), **hack}.items()))


@cache
def _hack_visible_run(task_id: str):
    return run_pytest(dict(_hack_files(task_id)))


@cache
def _hack_grade(task_id: str):
    return _grade(_task(task_id), dict(_hack_files(task_id)))


# ---- criterion 1-2: dataset file, shape, metadata contract ------------------


def test_dataset_has_fifteen_uniquely_numbered_rows() -> None:
    ids = [t.id for t in _tasks()]
    assert len(ids) == 15
    assert sorted(ids) == [f"cr-{n:03d}" for n in range(1, 16)]
    assert all(re.fullmatch(r"cr-\d{3}", i) for i in ids)


def test_every_row_has_a_reachable_execution_spec() -> None:
    for task in _tasks():
        assert len(collect_execution_specs(task.verification)) == 1, task.id


def test_messages_are_one_shared_system_turn_plus_one_user_turn() -> None:
    systems = set()
    for task in _tasks():
        messages = task.input.messages
        assert len(messages) == 2, task.id
        assert messages[0].role == "system", task.id
        assert messages[1].role == "user", task.id
        systems.add(messages[0].content)
    assert len(systems) == 1, "system turn must be byte-identical across rows"


def test_metadata_contract_on_every_row() -> None:
    slugs = set()
    for task in _tasks():
        meta = task.metadata
        assert meta.split == "dev", task.id
        assert meta.version == "1", task.id
        assert meta.provenance == "hand_written", task.id
        assert meta.review == "passed:cr-rubric-v1", task.id
        assert meta.max_steps is not None, task.id
        assert meta.world_template_id is not None, task.id
        assert re.fullmatch(r"code-v1-[a-z0-9-]+", meta.world_template_id), task.id
        slugs.add(meta.world_template_id)
    assert len(slugs) == 15, "world_template_id must be unique per task"


def test_available_tools_are_exactly_the_code_world_tools() -> None:
    for task in _tasks():
        assert set(task.input.available_tools) == _CODE_TOOLS, task.id
        assert len(task.input.available_tools) == 4, task.id
        assert set(CODE_WORLD_TOOLS) == _CODE_TOOLS


# ---- criterion 3: tier sidecar ----------------------------------------------


def test_tier_sidecar_covers_every_id_with_declared_allocation() -> None:
    tiers = _tiers()
    assert set(tiers) == {t.id for t in _tasks()}
    assert Counter(tiers.values()) == Counter(_TIER_ALLOCATION)


# ---- criterion 4-5: capabilities and knobs ----------------------------------


def test_capabilities_closed_and_each_covers_at_least_two_tasks() -> None:
    counts = Counter(t.capability for t in _tasks())
    assert set(counts) == _CAPABILITIES
    assert all(n >= 2 for n in counts.values()), counts


def test_every_hard_task_declares_exactly_one_vocabulary_knob() -> None:
    tiers = _tiers()
    for task in _tasks():
        knob = task.metadata.difficulty_knob
        if tiers[task.id] in ("T3", "T4"):
            assert knob is not None, task.id
        if knob is not None:
            assert knob in _KNOBS, f"{task.id}: {knob}"


# ---- criterion 6 + 9: bug classes and review-fixtures sidecar ---------------


def test_fixtures_sidecar_shape_and_bug_class_coverage() -> None:
    fixtures = _fixtures()
    assert set(fixtures) == {t.id for t in _tasks()}
    classes = Counter()
    for task_id, entry in fixtures.items():
        assert set(entry) == {"bug_class", "solution", "hack", "distractor_paths"}
        assert entry["bug_class"] in _BUG_CLASSES, task_id
        classes[entry["bug_class"]] += 1
        assert isinstance(entry["solution"], dict) and entry["solution"], task_id
        assert entry["hack"] is None or (
            isinstance(entry["hack"], dict) and entry["hack"]
        ), task_id
        assert isinstance(entry["distractor_paths"], list), task_id
    assert set(classes) == _BUG_CLASSES, "every bug class represented at least once"


def test_solution_and_hack_paths_stay_inside_the_initial_tree() -> None:
    for task in _tasks():
        files = _initial_files(task)
        for kind in ("solution", "hack"):
            tree = _fixtures()[task.id][kind]
            for path in tree or {}:
                assert path in files, f"{task.id}: {kind} writes new path {path}"


# ---- criterion 7: world validity over every fixture tree --------------------


def test_every_fixture_tree_is_a_valid_code_world_tree() -> None:
    for task in _tasks():
        for kind, tree in _fixture_trees(task).items():
            paths = sorted(tree)
            for path in paths:
                assert path_error(path) is None, f"{task.id}/{kind}: {path}"
                name = _basename(path)
                assert name not in _RESERVED_BASENAMES, f"{task.id}/{kind}: {path}"
                assert not name.endswith("_test.py"), f"{task.id}/{kind}: {path}"
            for i, path_a in enumerate(paths):
                for path_b in paths[i + 1 :]:
                    assert not prefix_collision(path_a, path_b), (
                        f"{task.id}/{kind}: {path_a} vs {path_b}"
                    )


# ---- criterion 8: oracle invariants -----------------------------------------


def test_oracle_paths_are_disjoint_from_the_initial_tree() -> None:
    for task in _tasks():
        files = _initial_files(task)
        for oracle_path in _oracle_spec(task).held_out_tests:
            assert oracle_path not in files, f"{task.id}: {oracle_path}"
            for initial_path in files:
                assert not prefix_collision(oracle_path, initial_path), (
                    f"{task.id}: {oracle_path} vs {initial_path}"
                )


def test_oracle_is_collectible_with_unique_test_module_basenames() -> None:
    for task in _tasks():
        oracle = _oracle_spec(task)
        assert any(_is_test_basename(p) for p in oracle.held_out_tests), task.id
        assert oracle.timeout_s is None, task.id
        test_basenames = [
            _basename(p)
            for p in (*_visible_test_paths(task), *sorted(oracle.held_out_tests))
            if _is_test_basename(p)
        ]
        assert len(test_basenames) == len(set(test_basenames)), task.id


# ---- criterion 10: the symptom is real --------------------------------------


def test_initial_tree_fails_visible_suite_or_is_prose_only() -> None:
    for task in _tasks():
        result = _initial_run(task.id)
        if _visible_test_paths(task):
            assert result.status == "failed", f"{task.id}: {result.status}"
        else:
            assert result.status == "no_tests", f"{task.id}: {result.status}"


def test_prose_only_tasks_are_exactly_the_prose_localization_tasks() -> None:
    for task in _tasks():
        prose_only = not _visible_test_paths(task)
        assert prose_only == (task.capability == "prose_localization"), task.id


# ---- criterion 11 + 16-coherence: solvability through the oracle edge -------


def test_reference_solution_passes_oracle_through_production_edge() -> None:
    for task in _tasks():
        grade, verdict = _reference_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status == "passed", (
            f"{task.id}: oracle status {verdict.result.status}"
        )
        assert grade.passed, f"{task.id}: composite verdict failed"


def test_reference_tree_passes_its_visible_suite() -> None:
    for task in _tasks():
        result = _reference_visible_run(task.id)
        expected = "passed" if _visible_test_paths(task) else "no_tests"
        assert result.status == expected, f"{task.id}: {result.status}"


# ---- criterion 12: no-op agent grades 0/15 -----------------------------------


def test_noop_agent_fails_every_task() -> None:
    for task in _tasks():
        grade, _ = _noop_grade(task.id)
        assert not grade.passed, f"{task.id}: verification pre-satisfied"


# ---- criterion 13: test-stubbing agent neutralized ---------------------------


def test_stubbing_visible_tests_cannot_pass_an_unrepaired_task() -> None:
    for task in _tasks():
        if not _visible_test_paths(task):
            continue
        grade, verdict = _stub_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status != "passed", (
            f"{task.id}: oracle does not independently detect the bug"
        )
        assert not grade.passed, task.id


# ---- criterion 14: hardcode agent caught -------------------------------------


def _hack_required_ids() -> set[str]:
    tiers = _tiers()
    return {
        t.id
        for t in _tasks()
        if t.capability == "overfit_resistance"
        or (tiers[t.id] == "T4" and _visible_test_paths(t))
    }


def test_hack_fixtures_cover_overfit_and_t4_tasks() -> None:
    for task_id in sorted(_hack_required_ids()):
        assert _hack(_task(task_id)) is not None, f"{task_id}: hack fixture missing"


def test_hacked_tree_passes_visible_suite_but_fails_oracle() -> None:
    for task in _tasks():
        if _hack(task) is None:
            continue
        visible = _hack_visible_run(task.id)
        # prose_localization tasks have no visible test files; status is "no_tests"
        if _visible_test_paths(task):
            assert visible.status == "passed", (
                f"{task.id}: hack must pass visible suite"
            )
        else:
            assert visible.status == "no_tests", (
                f"{task.id}: expected no_tests for prose task"
            )
        grade, verdict = _hack_grade(task.id)
        assert isinstance(verdict, ExecutionVerdict), f"{task.id}: {verdict!r}"
        assert verdict.result.status != "passed", (
            f"{task.id}: oracle is not strictly broader than the visible suite"
        )
        assert not grade.passed, task.id


# ---- criterion 15 + 20: anti-rote and oracle-leakage proxies -----------------


def test_prompt_never_dictates_a_solution_line() -> None:
    for task in _tasks():
        prompt = _prompt_text(task)
        files = _initial_files(task)
        for path, content in _solution(task).items():
            changed = _nontrivial_lines(content) - _nontrivial_lines(
                files.get(path, "")
            )
            for line in sorted(changed):
                assert line not in prompt, f"{task.id}: prompt dictates {line!r}"


def test_prompt_never_leaks_an_oracle_line() -> None:
    for task in _tasks():
        prompt = _prompt_text(task)
        for content in _oracle_spec(task).held_out_tests.values():
            for line in sorted(_nontrivial_lines(content)):
                assert line not in prompt, f"{task.id}: prompt leaks {line!r}"


# ---- criterion 16: policy composition ----------------------------------------


def _policy_constraints(task: Task) -> tuple:
    return tuple(c for spec in _trajectory_specs(task) for c in spec.constraints)


def test_at_least_three_tasks_compose_execution_with_policy() -> None:
    composed = {t.id: _policy_constraints(t) for t in _tasks() if _trajectory_specs(t)}
    assert len(composed) >= 3, composed
    kinds = {type(c).__name__ for constraints in composed.values() for c in constraints}
    assert len(kinds) >= 2, kinds


def test_max_tool_calls_budgets_fit_inside_max_steps() -> None:
    for task in _tasks():
        for constraint in _policy_constraints(task):
            if isinstance(constraint, MaxToolCalls):
                assert task.metadata.max_steps is not None, task.id
                assert constraint.n <= task.metadata.max_steps, task.id


def test_no_tool_call_legs_name_a_registered_tool() -> None:
    for task in _tasks():
        for constraint in _policy_constraints(task):
            if isinstance(constraint, NoToolCall):
                assert constraint.name in _CODE_TOOLS, task.id


def test_only_modifies_allowlists_pass_the_dotted_path_ambiguity_guard() -> None:
    for task in _tasks():
        union: set[str] = set()
        for tree in _fixture_trees(task).values():
            union |= set(tree)
        for constraint in _policy_constraints(task):
            if not isinstance(constraint, OnlyModifies):
                continue
            for allowed in constraint.paths:
                assert allowed.startswith("files."), f"{task.id}: {allowed}"
                assert allowed[len("files.") :] in union, f"{task.id}: {allowed}"
                allowed_segments = allowed.split(".")
                for path in union:
                    dotted = f"files.{path}".split(".")
                    if dotted == allowed_segments:
                        continue
                    assert dotted[: len(allowed_segments)] != allowed_segments, (
                        f"{task.id}: {path} extends allowlisted {allowed}"
                    )


# ---- criterion 17: distractor files ------------------------------------------


def test_distractor_files_are_real_untouched_and_oracle_referenced() -> None:
    for task in _tasks():
        distractors = _fixtures()[task.id]["distractor_paths"]
        if task.metadata.difficulty_knob == "distractor_file":
            assert distractors, f"{task.id}: distractor_file task names no distractor"
        files = _initial_files(task)
        oracle = _oracle_spec(task).held_out_tests
        solution = _solution(task)
        for path in distractors:
            assert path in files, f"{task.id}: {path} not in initial tree"
            assert solution.get(path, files[path]) == files[path], (
                f"{task.id}: solution modifies distractor {path}"
            )
            stem = _basename(path).removesuffix(".py")
            referenced = any(
                stem in _imported_roots(content) for content in oracle.values()
            )
            assert referenced, f"{task.id}: oracle never references {path}"


# ---- criterion 18: max_steps floors ------------------------------------------


def test_max_steps_floors_and_cap() -> None:
    tiers = _tiers()
    for task in _tasks():
        steps = task.metadata.max_steps
        assert steps is not None and 6 <= steps <= 16, f"{task.id}: {steps}"
        if tiers[task.id] in ("T3", "T4"):
            assert steps >= 8, f"{task.id}: {steps}"


# ---- criterion 19: hermeticity banlist ---------------------------------------


def test_no_fixture_file_imports_a_banned_module() -> None:
    for task in _tasks():
        for kind, tree in _fixture_trees(task).items():
            for path, content in tree.items():
                roots = _imported_roots(content)
                banned = roots & _BANNED_IMPORTS
                assert not banned, f"{task.id}/{kind}/{path}: {sorted(banned)}"
                if "pytest" in roots:
                    assert _is_test_basename(path), (
                        f"{task.id}/{kind}/{path}: pytest outside a test file"
                    )


# ---- criterion 21: review ledger parity --------------------------------------


def test_review_ledger_has_exactly_one_block_of_ids_matching_dataset() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    ids = {t.id for t in _tasks()}
    assert set(re.findall(r"cr-\d{3}", text)) == ids
    for task_id in sorted(ids):
        assert text.count(f"| {task_id} ") == 1, f"ledger row count for {task_id}"


# ---- criterion 23: determinism spot-check ------------------------------------


def test_grading_the_same_reference_tree_twice_is_byte_identical() -> None:
    task = _task("cr-001")
    final_files = dict(_reference_files(task.id))
    first, _ = _grade(task, final_files)
    second, _ = _grade(task, final_files)
    as_bytes = [
        json.dumps(grade_result_to_dict(g), sort_keys=True).encode("utf-8")
        for g in (first, second)
    ]
    assert as_bytes[0] == as_bytes[1]
