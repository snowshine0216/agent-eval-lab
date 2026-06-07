# Architecture

Agent Eval Lab uses a functional-core, imperative-shell architecture.

## Data Flow

```text
Task Definitions
      |
      v
Agent Runner (I/O) ---> Trace Records
      |                     |
      v                     v
Pure Graders ----------> Grade Results
      |                     |
      +----------+----------+
                 v
          Metrics and Reports
```

## Functional Core

The functional core contains deterministic transformations:

- validate task data;
- grade outputs and traces;
- aggregate metrics;
- classify failures;
- compare experiment results.

Core functions must not perform network calls, process execution, file access,
logging, or mutation of caller-owned data.

## Effectful Edges

Effectful edges are responsible for:

- invoking models and agents;
- executing tools and test commands;
- reading and writing datasets;
- persisting traces and reports;
- interacting with external services.

Effects should return explicit data that can be passed into the functional
core. Hidden shared state is avoided.

## Module Boundaries

Planned feature-oriented modules:

```text
agent_eval_lab/
  tasks/       Task schemas and validation
  graders/     Pure grading functions
  runs/        Run orchestration and trace records
  metrics/     Pure aggregation and comparison
  reports/     Report models and I/O
```

Each module should expose a small public interface, remain focused, and keep
files below roughly 200 lines where practical.

## Testing Strategy

- Unit tests cover pure functions without mocks.
- Integration tests cover I/O boundaries.
- Every behavior change begins with a failing test.
- Evaluation tasks and graders are reviewed together.
- Reproducibility checks ensure trials start from clean state.

## Initial Decision

The first grader is deterministic exact match. This creates the smallest useful
vertical slice and establishes the result data model before more subjective
graders are added.
