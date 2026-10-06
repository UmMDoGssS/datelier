from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest
from numpy.lib import format as npformat

from datelier.io.arrays.metadata import inspect_arrays, read_header
from datelier.io.types import ImportFailure


@pytest.mark.parametrize("version", [(1, 0), (2, 0), (3, 0)])
def test_header_versions_and_order_preserve_dtype_without_values(
    tmp_path: Path, version: tuple[int, int]
) -> None:
    dtype = np.dtype([("name" if version != (3, 0) else "tên", ">i8"), ("text", "U4")])
    array = np.zeros((3, 2), dtype=dtype, order="F")
    path = tmp_path / "records.npy"
    with path.open("wb") as stream:
        npformat.write_array(stream, array, version=version, allow_pickle=False)
    content = path.read_bytes()
    member = inspect_arrays(path).members[0]
    assert member.shape == (3, 2) and member.dtype == dtype and member.fortran_order
    assert member.raw_bytes == array.nbytes and member.usable
    assert member.header_bytes + member.raw_bytes == len(content)
    assert path.read_bytes() == content


@pytest.mark.parametrize("compressed", [False, True])
def test_archive_members_headers_only_include_empty_string_and_nonfinite_arrays(
    tmp_path: Path, compressed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "arrays.npz"
    values = {
        "images": np.zeros((4, 3, 2, 1), dtype=np.uint8),
        "labels": np.array(["café", "two", "three", "four"]),
        "empty": np.zeros((0, 5)),
        "values": np.array([np.nan, np.inf, -np.inf]),
    }
    (np.savez_compressed if compressed else np.savez)(path, **values)
    original = path.read_bytes()

    def forbid(*args: object, **kwargs: object) -> object:
        raise AssertionError("Metadata must not load payloads")

    monkeypatch.setattr(np, "load", forbid)
    catalog = inspect_arrays(path)
    assert [m.name for m in catalog.members] == list(values)
    for member in catalog.members:
        value = values[member.name]
        assert member.shape == value.shape and member.dtype == value.dtype
        assert member.raw_bytes == value.nbytes and member.compressed == compressed
        assert member.usable
    assert path.read_bytes() == original


def test_object_and_truncated_members_have_local_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "members.npz"
    payload = BytesIO()
    np.save(payload, np.arange(10), allow_pickle=False)
    objects = BytesIO()
    np.save(objects, np.array([{"x": 1}], dtype=object))
    with ZipFile(path, "w") as archive:
        archive.writestr("valid.npy", payload.getvalue())
        archive.writestr("truncated.npy", payload.getvalue()[:-2])
        archive.writestr("object.npy", objects.getvalue())
        archive.writestr("corrupt.npy", b"not numpy")
        archive.writestr("readme.txt", b"not an array")
    catalog = inspect_arrays(path)
    assert catalog.member("valid").usable
    assert (
        not catalog.member("truncated").usable
        and "truncated" in catalog.member("truncated").diagnostic
    )
    assert (
        not catalog.member("object").usable
        and "pickle" in catalog.member("object").diagnostic
    )
    assert not catalog.member("corrupt").usable and catalog.member("corrupt").diagnostic
    assert catalog.diagnostics == ("Ignored non-array member 'readme.txt'",)
    with pytest.raises(ValueError, match="unavailable"):
        catalog.member("missing")


def test_empty_archive_and_scalar_array(tmp_path: Path) -> None:
    empty = tmp_path / "empty.npz"
    with ZipFile(empty, "w"):
        pass
    assert inspect_arrays(empty).members == ()
    scalar = tmp_path / "scalar.npy"
    np.save(scalar, np.array(9, dtype=">i8"))
    member = inspect_arrays(scalar).members[0]
    assert (
        member.shape == () and member.raw_bytes == 8 and member.dtype == np.dtype(">i8")
    )


def test_header_length_limit_precedes_large_read_and_shape_validation() -> None:
    import struct

    class LimitedStream(BytesIO):
        def read(self, size: int | None = -1, /) -> bytes:
            assert size is not None and 0 <= size <= 10_000
            return super().read(size)

    with pytest.raises(ValueError, match="increase the header limit"):
        read_header(LimitedStream(b"\x93NUMPY\x02\x00" + struct.pack("<I", 2**31)))
    malformed = BytesIO()
    npformat.write_array_header_1_0(
        malformed, {"descr": "<f8", "fortran_order": False, "shape": (-1,)}
    )
    malformed.seek(0)
    with pytest.raises(ValueError, match="nonnegative"):
        read_header(malformed)


def test_duplicate_member_and_corrupt_source_are_actionable(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.npz"
    with ZipFile(path, "w") as archive:
        archive.writestr("x.npy", b"bad")
        with pytest.warns(UserWarning):
            archive.writestr("x.npy", b"bad")
    with pytest.raises(ImportFailure, match="Duplicate array member"):
        inspect_arrays(path)
    path.write_bytes(b"not a zip")
    with pytest.raises(ImportFailure, match="metadata"):
        inspect_arrays(path)
