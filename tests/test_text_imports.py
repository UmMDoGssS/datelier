"""Text records, tokenization and profiles must each work as the first import."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("entry", ["records", "tokenizers.prepare", "profiles"])
def test_text_entry_points_import_independently_without_gui_or_ml(
    entry: str,
) -> None:
    source = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys,importlib; sys.path.insert(0,sys.argv[1]); "
            "importlib.import_module('datelier.inspection.text.'+sys.argv[2]); "
            "assert not set(sys.modules) & "
            "{'sklearn','numba','torch','imgui_bundle'}; "
            "assert sys.argv[2]=='profiles' or "
            "'datelier.inspection.text.profiles.statistics' not in sys.modules",
            str(source),
            entry,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
