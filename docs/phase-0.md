# Phase 0 evidence

Recorded on 2026-10-04. This is feasibility evidence for Linux, not a v1
capacity or platform-support guarantee.

## M0.1 development baseline

The clean environment at `/tmp/datelier-baseline-env` was created with
`UV_PROJECT_ENVIRONMENT=/tmp/datelier-baseline-env uv sync --locked`.
CPython 3.14.7 was selected. The dev group installed Pyrefly 1.3.2, pytest 9.1.1,
and Ruff 0.16.10. Its `datelier` entry point printed `Hello from datelier!`
and exited successfully. Imports of all three dev tools passed.

Step checks:

```text
uv run pyrefly check          INFO 0 errors
uv run pytest                1 passed in 0.02s
uv run ruff check .          All checks passed!
uv run ruff format --check .  5 files already formatted
git diff --check             passed
```

Commands in this environment used `UV_CACHE_DIR=/tmp/datelier-uv-cache` because
the default cache is outside the writable sandbox. PyPI downloads ran with
approved network access; subsequent checks ran in the sandbox.
