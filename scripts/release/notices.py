"""Retain provider notices for runtime distributions and collected Ubuntu libraries."""

import shutil
import subprocess
import sysconfig
from importlib.metadata import Distribution, distribution
from pathlib import Path

from packaging.requirements import Requirement


def runtime_distributions() -> tuple[Distribution, ...]:
    pending = ["datelier", "torch", "pyinstaller"]
    found: dict[str, Distribution] = {}
    while pending:
        dist = distribution(pending.pop())
        name = dist.metadata["Name"]
        if name in found:
            continue
        found[name] = dist
        for item in dist.requires or ():
            requirement = Requirement(item)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    return tuple(found.values())


def collect_notices(
    destination: Path, native_inputs: list[str], portaudio: Path
) -> None:
    destination.mkdir(exist_ok=True)
    for dist in runtime_distributions():
        for member in dist.files or ():
            if any(
                part.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE"))
                for part in member.parts
            ):
                source = Path(str(dist.locate_file(member)))
                if source.is_file():
                    # Distribution records can contain paths outside site-packages.
                    safe_parts = tuple(part for part in member.parts if part != "..")
                    target = destination / dist.metadata["Name"] / Path(*safe_parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    system_inputs = [p for p in native_inputs if p.startswith(("/usr/", "/lib/"))]
    if system_inputs:
        result = subprocess.run(
            ["dpkg-query", "--search", *system_inputs], capture_output=True, text=True
        )
        packages = {
            line.split(": ", 1)[0].split(":", 1)[0]
            for line in result.stdout.splitlines()
            if ": /" in line
        }
        for name in sorted(packages):
            source = Path("/usr/share/doc") / name / "copyright"
            if source.is_file():
                target = destination / "system" / name
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target / "copyright")
    # Also cover a runtime extracted from an Ubuntu package without installation.
    copyright_file = portaudio.parents[2] / "share/doc/libportaudio2/copyright"
    if not copyright_file.is_file():
        raise FileNotFoundError(
            f"PortAudio provider notice is missing: {copyright_file}"
        )
    target = destination / "system/libportaudio2"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(copyright_file, target / "copyright")
    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    target = destination / "python"
    target.mkdir(exist_ok=True)
    shutil.copyfile(python_license, target / "LICENSE.txt")
