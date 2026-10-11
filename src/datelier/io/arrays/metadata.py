"""Bounded NPY headers and NPZ member metadata, without array materialization."""

import ast
import struct
from io import BytesIO
from math import prod
from pathlib import Path
from typing import BinaryIO, cast
from zipfile import ZIP_STORED, BadZipFile, ZipFile, is_zipfile

import numpy as np
from numpy.lib import format as npformat

from datelier.core import SourceReference
from datelier.inspection.arrays import ArrayCatalog, ArrayMember
from datelier.io.types import ImportFailure

DEFAULT_HEADER_BYTES = 10_000
type Header = tuple[tuple[int, ...], bool, np.dtype[np.generic]]


def read_header(
    source: BinaryIO, *, max_header_bytes: int = DEFAULT_HEADER_BYTES
) -> tuple[Header, int]:
    if not 1 <= max_header_bytes <= 16 * 1024 * 1024:
        raise ValueError("Header limit must be between one byte and 16 MiB")
    version = cast(tuple[int, int], npformat.read_magic(source))
    if version not in ((1, 0), (2, 0), (3, 0)):
        raise ValueError(f"Unsupported NPY version {version}")
    length_size = 2 if version == (1, 0) else 4
    length_bytes = source.read(length_size)
    if len(length_bytes) != length_size:
        raise ValueError("Truncated NPY header length")
    length = struct.unpack("<H" if length_size == 2 else "<I", length_bytes)[0]
    if length > max_header_bytes:
        raise ValueError(
            f"NPY header exceeds {max_header_bytes} bytes; increase the header limit"
        )
    header = source.read(length)
    if len(header) != length:
        raise ValueError("Truncated NPY header")
    # NumPy checks its limit after reading; check the binary length first.
    # Its public v2 reader expects latin1. For v3, retain Unicode field names
    # through an equivalent ASCII-escaped literal and validate with that reader.
    # Only the bounded header is normalized; payload bytes are never read here.
    if version == (3, 0):
        header = ascii(ast.literal_eval(header.decode("utf8"))).encode("ascii")
        length_bytes = struct.pack("<I", len(header))
    reader = (
        npformat.read_array_header_1_0
        if version == (1, 0)
        else npformat.read_array_header_2_0
    )
    shape, order, dtype = cast(
        Header,
        reader(
            BytesIO(length_bytes + header),
            max_header_size=max(max_header_bytes, len(header)),
        ),
    )
    if any(type(n) is not int or n < 0 for n in shape) or len(shape) > 64:
        raise ValueError("Array shape requires at most 64 nonnegative dimensions")
    raw_bytes = prod(shape) * dtype.itemsize
    if raw_bytes > 2**63 - 1:
        raise ValueError("Declared array storage exceeds supported address sizes")
    return (shape, order, dtype), 8 + length_size + length


def _member(
    source: BinaryIO,
    name: str,
    storage_name: str | None,
    container_bytes: int,
    stored_bytes: int,
    compressed: bool,
    max_header_bytes: int,
) -> ArrayMember:
    (shape, order, dtype), header_bytes = read_header(
        source, max_header_bytes=max_header_bytes
    )
    raw_bytes = prod(shape) * dtype.itemsize
    diagnostic = ""
    if dtype.hasobject:
        diagnostic = (
            "Object dtype payloads require pickle and cannot be inspected. "
            "Save a non-object array."
        )
    elif header_bytes + raw_bytes > container_bytes:
        diagnostic = (
            "Array payload is truncated; restore the source or choose another member."
        )
    return ArrayMember(
        name,
        storage_name,
        shape,
        dtype,
        order,
        header_bytes,
        raw_bytes,
        stored_bytes,
        container_bytes,
        compressed,
        diagnostic,
    )


def inspect_arrays(
    path: Path,
    *,
    max_header_bytes: int = DEFAULT_HEADER_BYTES,
    archive: bool | None = None,
) -> ArrayCatalog:
    path = path.expanduser().resolve()
    members: list[ArrayMember] = []
    diagnostics: list[str] = []
    try:
        before = path.stat()
        if (
            archive
            if archive is not None
            else (
                path.suffix.lower() == ".npz"
                or path.suffix.lower() != ".npy"
                and is_zipfile(path)
            )
        ):
            with ZipFile(path) as zip_source:
                seen: set[str] = set()
                for info in zip_source.infolist():
                    if info.is_dir() or not info.filename.endswith(".npy"):
                        diagnostics.append(
                            f"Ignored non-array member {info.filename!r}"
                        )
                        continue
                    name = info.filename[:-4]
                    if name in seen:
                        raise ValueError(
                            f"Duplicate array member {name!r}; rename archive members"
                        )
                    seen.add(name)
                    try:
                        with zip_source.open(info) as stream:
                            member = _member(
                                cast(BinaryIO, stream),
                                name,
                                info.filename,
                                info.file_size,
                                info.compress_size,
                                info.compress_type != ZIP_STORED,
                                max_header_bytes,
                            )
                    except (ValueError, OSError, BadZipFile, EOFError) as error:
                        member = ArrayMember(
                            name,
                            info.filename,
                            stored_bytes=info.compress_size,
                            container_bytes=info.file_size,
                            diagnostic=str(error),
                        )
                    members.append(member)
        else:
            with path.open("rb") as stream:
                members.append(
                    _member(
                        stream,
                        "$",
                        None,
                        before.st_size,
                        before.st_size,
                        False,
                        max_header_bytes,
                    )
                )
        after = path.stat()
    except (ValueError, OSError, BadZipFile, EOFError, RecursionError) as error:
        raise ImportFailure(
            path, f"Could not read array metadata: {str(error)[:1200]}"
        ) from error
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ImportFailure(
            path, "Source changed while reading array metadata; reload it"
        )
    return ArrayCatalog(
        SourceReference(path, after.st_size, after.st_mtime_ns),
        tuple(members),
        tuple(diagnostics),
    )
