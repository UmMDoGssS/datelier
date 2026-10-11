"""Run current native acceptance harnesses serially on a Linux display."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-native-acceptance")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scripts = Path(__file__).resolve().parent
    commands = [(path.name, []) for path in sorted(scripts.glob("rebuild_*_smoke.py"))]
    commands.append(("rebuild_annotations_smoke.py", ["--distinct"]))
    if args.matrix:
        for width, height in ((1024, 768), (1280, 800), (1600, 1000)):
            for theme in ("Dark", "Light", "Classic"):
                for script in ("rebuild_gui_smoke.py", "rebuild_media_matrix.py"):
                    commands.append(
                        (
                            script,
                            [
                                "--width",
                                str(width),
                                "--height",
                                str(height),
                                "--theme",
                                theme,
                                "--output",
                                str(args.output / f"{script}-{width}-{theme}"),
                            ],
                        )
                    )
    env = {**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1", "POLARS_MAX_THREADS": "8"}
    reports: list[dict[str, object]] = []
    report_path = args.output / "native-acceptance.json"
    if args.resume and report_path.exists():
        previous: list[dict[str, object]] = json.loads(report_path.read_text())
        for index, report in enumerate(previous):
            if report["return_code"] != 0:
                break
            name, options = commands[index]
            if report["command"] != [name, *options]:
                raise ValueError("Saved acceptance commands differ from this run")
            reports.append(report)
    for index, (name, options) in enumerate(commands):
        if index < len(reports):
            continue
        started = perf_counter()
        command = [sys.executable, str(scripts / name), *options]
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
        print(f"{index + 1}/{len(commands)} {name}: {result.returncode}", flush=True)
        result.check_returncode()


if __name__ == "__main__":
    main()
