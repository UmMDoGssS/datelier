"""Run the current native acceptance inventory serially on a Linux display.

From the checkout::

    uv run python -m scripts.gui.acceptance --list --matrix
    uv run python -m scripts.gui.acceptance --matrix --output /tmp/datelier-native

--list inventories commands without importing GUI/optional runtimes. Normal runs
select Mesa software rendering and eight Polars threads, saving per-command logs
and native-acceptance.json. --matrix adds shell/media checks at 1024x768, 1280x800,
and 1600x1000 in Dark/Light/Classic. --resume requires the same options/output and
validates the saved inventory before skipping successful commands. Resource and
real-output-device probes remain separate from this native interaction inventory.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from time import perf_counter


def commands(matrix: bool, output: Path) -> list[tuple[str, list[str]]]:
    """Discover native checks without importing GUI or optional runtimes."""
    modules = sorted(
        f"scripts.gui.{path.stem}"
        for path in Path(__file__).resolve().parent.glob("*.py")
        if path.stem not in {"__init__", "acceptance"}
    )
    result = [(module, []) for module in modules]
    result.append(("scripts.gui.annotations", ["--distinct"]))
    if matrix:
        for width, height in ((1024, 768), (1280, 800), (1600, 1000)):
            for theme in ("Dark", "Light", "Classic"):
                for name in ("workbench", "media_matrix"):
                    result.append(
                        (
                            f"scripts.gui.{name}",
                            [
                                "--width",
                                str(width),
                                "--height",
                                str(height),
                                "--theme",
                                theme,
                                "--output",
                                str(output / f"{name}-{width}-{theme}"),
                            ],
                        )
                    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--list", action="store_true", help="list commands without running"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-native-acceptance")
    )
    args = parser.parse_args()
    inventory = commands(args.matrix, args.output)
    if args.list:
        for name, options in inventory:
            print(shlex.join([sys.executable, "-m", name, *options]))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1", "POLARS_MAX_THREADS": "8"}
    reports: list[dict[str, object]] = []
    report_path = args.output / "native-acceptance.json"
    if args.resume and report_path.exists():
        previous: list[dict[str, object]] = json.loads(report_path.read_text())
        if len(previous) > len(inventory):
            raise ValueError("Saved acceptance inventory differs from this run")
        for index, report in enumerate(previous):
            if report["return_code"] != 0:
                break
            name, options = inventory[index]
            if report["command"] != [name, *options]:
                raise ValueError("Saved acceptance commands differ from this run")
            reports.append(report)
    for index, (name, options) in enumerate(inventory):
        if index < len(reports):
            continue
        started = perf_counter()
        command = [sys.executable, "-m", name, *options]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300, env=env
        )
        log = args.output / f"{index:02d}-{name}.log"
        log.write_text(result.stdout + result.stderr)
        reports.append(
            {
                "command": [name, *options],
                "return_code": result.returncode,
                "seconds": perf_counter() - started,
                "log": str(log),
            }
        )
        report_path.write_text(json.dumps(reports, indent=2) + "\n")
        print(f"{index + 1}/{len(inventory)} {name}: {result.returncode}", flush=True)
        result.check_returncode()


if __name__ == "__main__":
    main()
