"""Deterministic metadata-only media directory membership and fingerprints."""

import hashlib
import os
from pathlib import Path

from datelier.core.column_roles import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
)

MEDIA_EXTENSIONS = (*IMAGE_EXTENSIONS, *AUDIO_EXTENSIONS, *TEXT_EXTENSIONS)


def media_members(root: Path, recursive: bool = True) -> tuple[str, ...]:
    result: list[str] = []

    def fail(error: OSError) -> None:
        raise error

    for directory, folders, files in os.walk(root, followlinks=False, onerror=fail):
        folders[:] = (
            sorted(f for f in folders if f not in (".git", ".venv", "node_modules"))
            if recursive
            else []
        )
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() in MEDIA_EXTENSIONS:
                result.append(path.relative_to(root).as_posix())
    return tuple(sorted(result))


def directory_signature(root: Path) -> tuple[int, int, str]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    size = modified = 0
    for member in media_members(root):
        path = root / member
        try:
            stat = path.stat()
            signature = (member, stat.st_size, stat.st_mtime_ns)
            size += stat.st_size
            modified = max(modified, stat.st_mtime_ns)
        except FileNotFoundError:
            signature = (member, None, None)
        digest.update(repr(signature).encode())
    return size, modified, digest.hexdigest()
