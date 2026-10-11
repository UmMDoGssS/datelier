"""Cold mixed-corpus/long-record native gates with predeclared resource budgets."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
from native_text_resources import measure_mixed

BUDGETS = {
    "metadata_ms": 3000,
    "comparison_ms": 20000,
    "long_record_ms": 3000,
    "frame_p95_ms": 33,
    "long_prepare_frame_p95_ms": 33,
    "peak_rss_mib": 768,
    "comparison_retained_bytes": 8 * 2**20,
    "rendered_frequency_rows": 20,
    "rendered_token_rows": 30,
    "source_page_code_points": 2048,
    "workers": 4,
    "temporary_bytes": 0,
}


def measure(root: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    return measure_mixed(root, BUDGETS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-text-mixed"))
    args = parser.parse_args()
    if args.root:
        print(json.dumps(measure(args.root, args.output)))
        return
    with TemporaryDirectory(prefix="datelier-text-mixed-") as directory:
        root = Path(directory)
        for name in ("a", "b"):
            pl.DataFrame(
                {
                    "id": range(50000),
                    "text": [
                        None
                        if i % 100 == 0
                        else ""
                        if i % 100 == 1
                        else f"alpha beta beta gamma δ 中 e\u0301 word{i % 100}"
                        for i in range(50000)
                    ],
                }
            ).write_parquet(root / f"{name}.parquet")
        text = "A e\u0301 中🙂\n" + "long original text 中🙂\n" * 5000 + "FINAL"
        pl.DataFrame({"id": [1], "text": [text]}).write_parquet(root / "long.parquet")
        sources = tuple(
            root / name for name in ("a.parquet", "b.parquet", "long.parquet")
        )
        digests = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--root",
                str(root),
                "--output",
                str(args.output),
            ],
            capture_output=True,
            text=True,
        )
        if child.returncode:
            raise RuntimeError(child.stderr)
        assert digests == [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        report = json.loads(child.stdout.strip().splitlines()[-1])
        report["sources_preserved"] = True
        (args.output / "text-mixed-resources.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
