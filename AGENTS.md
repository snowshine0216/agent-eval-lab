# Repository Instructions

## Functional Programming

- Keep deterministic transformations pure.
- Do not perform I/O or logging inside pure functions.
- Never mutate function arguments or shared module state.
- Pass dependencies explicitly and return transformed data.
- Prefer small composable functions over stateful classes.

## Organization

- Group code by feature.
- Keep modules focused and below 200 lines where practical.
- Keep functions below 20 lines where practical.
- Keep I/O at explicit boundaries.

## Test-Driven Development

- Write a failing test before implementation.
- Implement only enough behavior to pass the test.
- Refactor only while tests remain green.
- Mirror source test paths where practical.

## Validation

Run before committing:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
