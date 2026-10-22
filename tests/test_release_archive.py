"""Release extraction preserves native aliases/modes and excludes the probe."""

import json
import tarfile
from pathlib import Path

import pytest

from scripts.release.archive import package, sha256
from scripts.release.verify import verify


def bundle(root: Path) -> Path:
    path = root / "bundle"
    (path / "_internal").mkdir(parents=True)
    (path / "build-manifest.json").write_text(json.dumps({"version": "1.0.0"}))
    (path / "datelier").write_bytes(b"application")
    (path / "datelier").chmod(0o755)
    (path / "datelier-verify").write_bytes(b"repository probe")
    (path / "_internal/libreal.so.2.0").write_bytes(b"native library")
    (path / "_internal/libreal.so.2").symlink_to("libreal.so.2.0")
    return path


def test_release_round_trip_preserves_links_permissions_and_checksum(
    tmp_path: Path,
) -> None:
    source = bundle(tmp_path)
    archive = package(source, tmp_path / "release")
    with tarfile.open(archive) as stream:
        assert "datelier/datelier-verify" not in stream.getnames()
        assert stream.getmember("datelier/_internal/libreal.so.2").issym()
        stream.extractall(tmp_path / "installed", filter="data")
    installed = tmp_path / "installed/datelier"
    assert (installed / "datelier").stat().st_mode & 0o111 == 0o111
    assert (installed / "_internal/libreal.so.2").read_bytes() == b"native library"
    assert (
        archive.parent / "SHA256SUMS"
    ).read_text() == f"{sha256(archive)}  {archive.name}\n"
    assert (source / "datelier-verify").read_bytes() == b"repository probe"


@pytest.mark.parametrize("absolute", [False, True])
def test_reject_nonportable_or_escaping_library_links(
    tmp_path: Path, absolute: bool
) -> None:
    source = bundle(tmp_path)
    outside = tmp_path / "outside.so"
    outside.write_bytes(b"external")
    (source / "_internal/bad.so").symlink_to(
        outside if absolute else "../../outside.so"
    )
    with pytest.raises(ValueError, match="relative and stay inside"):
        package(source, tmp_path / "release")
    assert outside.read_bytes() == b"external"


def test_checksum_failure_leaves_the_installation_destination_untouched(
    tmp_path: Path,
) -> None:
    archive = package(bundle(tmp_path), tmp_path / "release")
    archive.write_bytes(b"damaged archive")
    output = tmp_path / "install"
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify(archive, tmp_path / "unused-probe", output, native=False)
    assert not output.exists()
