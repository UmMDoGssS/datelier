"""Repository-only verification tools, run from the checkout with python -m.

Install development dependencies with ``uv sync --locked``. The normal checks are::

    uv run pyrefly check --min-severity warn
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

``gui`` owns serial native interaction/restoration checks; ``benchmarks`` owns
measured timing/memory/source-preservation gates; ``environment`` probes real
codecs/devices/optional CPU dependencies; ``installation`` verifies installed
wheels; ``release`` builds and verifies the frozen Linux bundle.
``support`` supplies shared fixtures/input/instrumentation. These tools
stay outside the application wheel. Consult each module's docstring and --help
before running resource-intensive or real-device checks.

The synthetic feasibility CLI and widget-patching harnesses are retired. Current
coverage is discoverable with ``python -m scripts.gui.acceptance --list --matrix``
and behavioral tests. Historical evidence is in Git snapshot b1b332c; recover old
harness source from 9a6a808 and use its matching pre-overhaul checkout 13c0e58 to
run it. Retiring a harness does not close deferred human listening/usability gates.
"""
