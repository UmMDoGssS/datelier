"""Exercise repository tool entry points and their real child processes."""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_acceptance_inventory_lists_checks_without_loading_the_app(
    tmp_path: Path,
) -> None:
    output = tmp_path / "not-created"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; "
            "runpy.run_module('scripts.gui.acceptance', run_name='__main__'); "
            "assert not any(name.startswith(('datelier', 'imgui_bundle', 'sklearn')) "
            "for name in sys.modules)",
            "--list",
            "--matrix",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    commands = result.stdout.splitlines()
    assert any("-m scripts.gui.analysis_schema" in line for line in commands)
    assert sum("-m scripts.gui.media_matrix" in line for line in commands) == 10
    assert any("--distinct" in line for line in commands)
    assert not any("scripts.environment" in line for line in commands)
    assert not output.exists()


@pytest.mark.parametrize("name", ["inspection", "formats", "operations", "exploration"])
def test_benchmark_parent_runs_relocated_worker(
    name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_name = f"scripts.benchmarks.{name}"
    module = importlib.import_module(module_name)
    output = tmp_path / "report.json"
    arguments = [module_name, "--output", str(output)]
    monkeypatch.setattr(module, "CASES", ((256, 3),))
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setenv("POLARS_MAX_THREADS", "2")
    module.main()
    report = json.loads(output.read_text())
    assert report["measurements"]
    assert all(item["rows"] == 256 for item in report["measurements"])
