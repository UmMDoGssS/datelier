"""Build the locked CPU bundle; write host/version provenance beside its libraries.

The checkout, interpreter and native dependency wheels determine the artifact.
The build manifest records them; byte-identical builds are not promised. No Git
tags, remote releases, uploads, or application preferences are changed here.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from scripts.release.notices import collect_notices


def source_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = [root / "pyproject.toml", root / "uv.lock"]
    files.extend((root / "src").rglob("*.py"))
    files.extend((root / "scripts/release").rglob("*.py"))
    files.extend((root / "scripts/release").glob("*.spec"))
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/frozen"))
    parser.add_argument(
        "--portaudio-library",
        type=Path,
        default=Path("/usr/lib/x86_64-linux-gnu/libportaudio.so.2"),
        help="system or extracted Ubuntu libportaudio2 runtime",
    )
    args = parser.parse_args()
    if sys.platform != "linux" or platform.machine() != "x86_64":
        parser.error("The release build currently targets Linux x86-64")
    if "+cpu" not in version("torch"):
        parser.error("Install the locked CPU checkpoint extra before building")
    portaudio = args.portaudio_library.resolve()
    if not portaudio.is_file():
        parser.error("Install libportaudio2 or supply --portaudio-library")
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    work = root / "build/frozen"
    work.mkdir(parents=True, exist_ok=True)
    log = work / "pyinstaller.log"
    print(f"Building Datelier {version('datelier')}; build log: {log}", flush=True)
    with log.open("w") as stream:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                "--distpath",
                str(output),
                "--workpath",
                str(work),
                str(root / "scripts/release/datelier.spec"),
            ],
            cwd=root,
            env={
                **os.environ,
                "PYINSTALLER_CONFIG_DIR": str(work / "cache"),
                "DATELIER_PORTAUDIO_LIBRARY": str(portaudio),
            },
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    if result.returncode:
        print("\n".join(log.read_text().splitlines()[-60:]), file=sys.stderr)
        result.check_returncode()
    bundle = output / "datelier"
    packages = (
        "datelier",
        "imgui-bundle",
        "numpy",
        "polars",
        "scikit-learn",
        "scipy",
        "threadpoolctl",
        "umap-learn",
        "numba",
        "llvmlite",
        "pillow",
        "pyyaml",
        "sounddevice",
        "soundfile",
        "tokenizers",
        "torch",
        "pyinstaller",
        "pyinstaller-hooks-contrib",
    )
    manifest = {
        "version": version("datelier"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "os_release": platform.freedesktop_os_release(),
        "libc": platform.libc_ver(),
        "packages": {name: version(name) for name in packages},
        "checkpoint_support": "CPU only",
        "source_sha256": source_digest(root),
        "lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "portaudio_sha256": hashlib.sha256(portaudio.read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=root, text=True
            ).strip()
        ),
    }
    (bundle / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    collect_notices(
        bundle / "licenses",
        json.loads((work / "native-inputs.json").read_text()),
        portaudio,
    )
    print(f"Built {bundle}", flush=True)


if __name__ == "__main__":
    main()
