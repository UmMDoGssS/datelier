# Datelier

A personal Linux desktop workbench for in-memory tabular, structured, text,
image, and audio inspection. Data tables must fit in memory.

The Linux bundle includes Python, its dependencies, and CPU checkpoint support.
Extract `datelier-1.0.0-linux-x86_64.tar.gz`, keep the folder together, and launch:

```sh
./datelier/datelier /path/to/data.csv
./datelier/datelier --version
```

The tested binary target is Ubuntu 26.04 x86-64 with glibc 2.43 and a graphical
session with OpenGL. Older distributions are unverified. Mesa software rendering
is verified; select it with `LIBGL_ALWAYS_SOFTWARE=1`. Audio output requires a
working host output service/device. Multilingual fonts use the host's Noto Sans
and Noto Sans CJK (`fonts-noto-core` and `fonts-noto-cjk` on Ubuntu); emoji is
bundled. Accelerated rendering, human audio listening, and the unaided Titanic
usability targets remain unverified.

From source, install Python 3.14+ and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked --no-dev
uv run --no-dev datelier /path/to/data.csv
```

Omit the path for Welcome. Use `--workspace /path/to/session.datelier` to restore
a session. Workspaces reference sources; keep those files available. For setup
details and current behavior, start with the docstring in
[datelier](src/datelier/__init__.py) and the relevant subsystem package.
Development commands live in [scripts](scripts/__init__.py), and frozen build
commands in [scripts.release](scripts/release/__init__.py); contributor rules
remain in [AGENTS.md](AGENTS.md).

Historical milestone reports and evidence remain available in Git at `b1b332c`.
