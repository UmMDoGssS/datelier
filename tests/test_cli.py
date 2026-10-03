import subprocess
import sys
from pathlib import Path


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
