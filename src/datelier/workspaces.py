"""Atomic workspace I/O and source fingerprinting, intended for worker threads."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

from datelier.dataset import SourceReference
from datelier.recipe_codec import decode_record, encode
from datelier.workspace_types import Workspace, WorkspaceSource

MAX_WORKSPACE_BYTES = 2 * 1024 * 1024


def fingerprint(path: Path) -> WorkspaceSource:
    path = path.expanduser().resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ValueError("Source changed while checking it; retry")
    return WorkspaceSource(
        str(path), after.st_size, after.st_mtime_ns, digest.hexdigest()
    )


def reference_source(source: SourceReference) -> WorkspaceSource:
    result = fingerprint(source.path)
    if (result.size_bytes, result.modified_ns) != (
        source.size_bytes,
        source.modified_ns,
    ):
        raise ValueError("Source changed since import; reopen it before saving")
    return result


def atomic_write(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_workspace(path: Path, workspace: Workspace) -> None:
    path = path.expanduser().resolve()
    source = Path(workspace.source.path).expanduser().resolve()
    if path == source or path.exists() and path.samefile(source):
        raise ValueError("A workspace cannot overwrite its source data")
    workspace.validate()
    relative = replace(workspace.source, path=os.path.relpath(source, path.parent))
    text = json.dumps(
        encode(replace(workspace, source=relative)), indent=2, allow_nan=False
    )
    if len(text.encode("utf8")) > MAX_WORKSPACE_BYTES:
        raise ValueError("Workspace exceeds the 2 MiB recipe limit")
    atomic_write(path, text + "\n")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate workspace field: {key}")
        result[key] = value
    return result


def read_workspace(path: Path) -> Workspace:
    path = path.expanduser().resolve()
    with path.open("rb") as stream:
        content = stream.read(MAX_WORKSPACE_BYTES + 1)
    if len(content) > MAX_WORKSPACE_BYTES:
        raise ValueError("Workspace exceeds the 2 MiB recipe limit")

    def reject_constant(value: str) -> object:
        raise ValueError(f"Invalid JSON number: {value}")

    try:
        raw = cast(
            object,
            json.loads(
                content,
                object_pairs_hook=_unique_object,
                parse_constant=reject_constant,
            ),
        )
        workspace = decode_record(Workspace, raw)
        workspace.validate()
    except (UnicodeError, RecursionError, TypeError) as error:
        raise ValueError(f"Invalid workspace: {error}") from error
    source = replace(
        workspace.source, path=str((path.parent / workspace.source.path).resolve())
    )
    return replace(workspace, source=source)
