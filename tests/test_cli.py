import subprocess
import sys
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
    assert "--feasibility" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--smoke-frames", "-1"], "nonnegative"),
        (["example.csv", "--feasibility"], "Choose a CSV or --feasibility"),
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
