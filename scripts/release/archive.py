"""Package a one-folder bundle with portable symlinks and a SHA-256 file.

The repository verification executable is excluded. Members retain executable
permissions; links cannot point outside datelier/. The manifest identifies the
source/dependency snapshot, including dirty development builds. Final release
builds should come from a clean commit.
"""

import argparse
import hashlib
import json
import os
import re
import tarfile
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package(bundle: Path, output: Path) -> Path:
    bundle = bundle.resolve()
    manifest = json.loads((bundle / "build-manifest.json").read_text())
    release = manifest.get("version")
    if not isinstance(release, str) or not re.fullmatch(r"\d+\.\d+\.\d+", release):
        raise ValueError("The bundle requires a stable numeric release version")
    if not (bundle / "datelier").is_file():
        raise ValueError("The bundle has no datelier executable")
    for path in bundle.rglob("*"):
        if path.is_symlink() and (
            Path(os.readlink(path)).is_absolute()
            or not path.resolve().is_relative_to(bundle)
            or not path.exists()
        ):
            raise ValueError("Bundle links must be relative and stay inside the bundle")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"datelier-{release}-linux-x86_64.tar.gz"

    def member(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        if info.name == "datelier/datelier-verify":
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    with tarfile.open(archive, "w:gz", dereference=False) as stream:
        stream.add(bundle, arcname="datelier", filter=member)
    (output / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("dist/frozen/datelier"))
    parser.add_argument("--output", type=Path, default=Path("dist/release"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    (args.bundle / "README.md").write_text((root / "README.md").read_text())
    print(package(args.bundle, args.output))


if __name__ == "__main__":
    main()
