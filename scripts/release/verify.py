"""Extract and exercise the archive with no Python/compiler executables on PATH.

Use --native on a Linux display for the GUI/renderer gate. Fixtures, preferences,
JIT caches, logs and reports live only under --output, outside the checkout. The
separate verification helper must match the manifest; it is copied in after
extraction and is not part of the shipped archive. No audio device is opened.
"""

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from scripts.release.archive import sha256


def verify(archive: Path, probe: Path, output: Path, *, native: bool) -> None:
    checksums = {
        name: digest
        for digest, name in (
            line.split(maxsplit=1)
            for line in (archive.parent / "SHA256SUMS").read_text().splitlines()
        )
    }
    if checksums.get(archive.name) != sha256(archive):
        raise ValueError("Release archive checksum mismatch")
    output = output.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Verify the archive outside the checkout")
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        stream.extractall(output, filter="data")
    bundle = output / "datelier"
    assert not (bundle / "datelier-verify").exists()
    manifest = json.loads((bundle / "build-manifest.json").read_text())
    assert sha256(bundle / "datelier") == manifest["executables"]["datelier"]
    assert sha256(probe) == manifest["executables"]["datelier-verify"]
    shutil.copy2(probe, bundle / "datelier-verify")
    empty_path = output / "empty-path"
    empty_path.mkdir()
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV"}
    }
    env.update(
        PATH=str(empty_path),
        XDG_CONFIG_HOME=str(output / "config"),
        XDG_CACHE_HOME=str(output / "cache"),
        NUMBA_CACHE_DIR=str(output / "cache/numba"),
        POLARS_MAX_THREADS="8",
        LIBGL_ALWAYS_SOFTWARE="1",
    )

    def run(name: str, command: list[str]) -> None:
        result = subprocess.run(
            command, cwd=output, env=env, capture_output=True, text=True, timeout=300
        )
        (output / f"{name}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            print(result.stdout + result.stderr)
            result.check_returncode()

    run("version", [str(bundle / "datelier"), "--version"])
    run("help", [str(bundle / "datelier"), "--help"])
    command = [str(bundle / "datelier-verify"), "--output", str(output / "fixtures")]
    if native:
        command.append("--native")
    run("workflows", command)
    report = json.loads((output / "fixtures/frozen-verification.json").read_text())
    report.update(
        archive_sha256=sha256(archive),
        empty_path=True,
        source_commit=manifest["source_commit"],
        source_tree_dirty=manifest["source_tree_dirty"],
    )
    (output / "release-verification.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--probe", type=Path, default=Path("dist/frozen/datelier/datelier-verify")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    verify(
        args.archive.resolve(), args.probe.resolve(), args.output, native=args.native
    )


if __name__ == "__main__":
    main()
