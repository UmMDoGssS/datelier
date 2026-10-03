# Datelier

A Linux desktop data inspection workbench for analysts, targeting Python 3.14+.
The application is under development; Phase 0 establishes stack feasibility.
See [ROADMAP.md](ROADMAP.md) for delivery gates and [AGENTS.md](AGENTS.md) for
contributor conventions.

## Development

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --locked
uv run datelier
uv run pyrefly check
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv sync` installs the default `dev` group with Pyrefly, pytest, and Ruff.
Use `uv sync --no-dev` for runtime dependencies alone.
