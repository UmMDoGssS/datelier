import subprocess
import sys
from pathlib import Path


def test_installed_cli_launches() -> None:
    result = subprocess.run(
        [str(Path(sys.executable).parent / "datelier")],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == "Hello from datelier!\n"
    assert result.stderr == ""
