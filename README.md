# Datelier

A personal Linux desktop workbench for in-memory tabular, structured, text,
image, and audio inspection. Requires Python 3.14+, [uv](https://docs.astral.sh/uv/),
and a graphical session with OpenGL.

```sh
uv sync --locked --no-dev
uv run --no-dev datelier /path/to/data.csv
```

Omit the path for Welcome. Use `--workspace /path/to/session.datelier` to restore
a session. For setup details and current behavior, start with the docstring in
[datelier](src/datelier/__init__.py) and the relevant subsystem package.
Development commands live in [scripts](scripts/__init__.py); contributor rules
remain in [AGENTS.md](AGENTS.md).

Historical milestone reports and evidence remain available in Git at `b1b332c`.
