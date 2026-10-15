"""Cold native exact-corpus resource and UI gates with predeclared budgets."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl

from scripts.support.text_resources import measure_profile

BUDGETS = {
    "metadata_ms": 3000,
    "profile_ms": 20000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 768,
    "profile_retained_bytes": 8 * 2**20,
    "rendered_frequency_rows": 20,
    "workers": 4,
    "temporary_bytes": 0,
}


def measure(source: Path, output: Path, *, snapshot: bool = False) -> dict[str, object]:
    return measure_profile(source, BUDGETS, snapshot)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-resources")
    )
    args = parser.parse_args()
    if args.source:
        print(json.dumps(measure(args.source, args.output, snapshot=args.snapshot)))
        return
    with TemporaryDirectory(prefix="datelier-text-profile-") as directory:
        source = Path(directory) / "corpus.parquet"
        pl.DataFrame(
            {
                "id": range(100000),
                "text": [
                    None
                    if i % 100 == 0
                    else ""
                    if i % 100 == 1
                    else f"alpha beta beta gamma δ 中 e\u0301 word{i % 100}"
                    for i in range(100000)
                ],
            }
        ).write_parquet(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.benchmarks.text_profiles",
                "--source",
                str(source),
                "--output",
                str(args.output),
                *(["--snapshot"] if args.snapshot else []),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr)
        report = json.loads(completed.stdout.strip().splitlines()[-1])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        report["source_preserved"] = True
        args.output.mkdir(parents=True, exist_ok=True)
        (
            args.output
            / (
                "text-profile-snapshot.json"
                if args.snapshot
                else "text-profile-resources.json"
            )
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
