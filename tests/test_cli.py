import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest


def test_installed_cli_launches() -> None:
    result = subprocess.run(
        [str(Path(sys.executable).parent / "datelier"), "--help"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert "Datelier data inspection workbench" in result.stdout
    assert "--feasibility" not in result.stdout
    assert "--workspace" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("entry", ["console", "module"])
def test_version_identifies_the_installed_build(entry: str) -> None:
    command = (
        [str(Path(sys.executable).parent / "datelier")]
        if entry == "console"
        else [sys.executable, "-m", "datelier"]
    )
    result = subprocess.run(
        [*command, "--version"], capture_output=True, text=True, check=True, timeout=10
    )
    assert result.stdout.strip().endswith(f" {version('datelier')}")
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--smoke-frames", "-1"], "nonnegative"),
        (["example.csv", "--workspace", "example.datelier"], "Choose a dataset"),
        (["--feasibility"], "unrecognized arguments: --feasibility"),
    ],
)
def test_invalid_cli_arguments_fail_before_gui_launch(
    arguments: list[str], message: str
) -> None:
    result = subprocess.run(
        [str(Path(sys.executable).parent / "datelier"), *arguments],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert message in result.stderr
