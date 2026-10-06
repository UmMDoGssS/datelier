"""Worker-only reference indexing: exact paths win; ambiguity is never guessed."""

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock

from datelier.inspection.references.types import (
    AssetIdentity,
    ReferenceSettings,
    Resolution,
)


class IndexProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._count = 0

    def add(self) -> None:
        with self._lock:
            self._count += 1

    @property
    def count(self) -> int:
        with self._lock:
            return self._count


@dataclass(frozen=True)
class ReferenceIndex:
    names: dict[str, tuple[Path, ...]]
    stems: dict[str, tuple[Path, ...]]
    diagnostics: tuple[str, ...] = ()


def discover(
    source: Path, settings: ReferenceSettings, stop: Event, progress: IndexProgress
) -> ReferenceIndex:
    settings.validate()
    roots = tuple(Path(r).expanduser().resolve() for r in settings.roots) or (
        source.parent,
        source.parent.parent,
    )
    names: dict[str, set[Path]] = {}
    stems: dict[str, set[Path]] = {}
    seen: set[Path] = set()
    diagnostics: list[str] = []
    for root in roots:
        if stop.is_set():
            break
        if not root.is_dir():
            diagnostics.append(f"Root unavailable: {root}")
            continue

        def on_error(error: OSError) -> None:
            if len(diagnostics) < 20:
                diagnostics.append(f"Directory unreadable: {error}")

        for directory, folders, files in os.walk(
            root, followlinks=False, onerror=on_error
        ):
            if stop.is_set():
                break
            folders[:] = sorted(
                f for f in folders if f not in (".git", ".venv", "node_modules")
            )
            for name in sorted(files):
                if stop.is_set():
                    break
                path = Path(directory) / name
                if (
                    settings.extensions
                    and path.suffix.lower() not in settings.extensions
                ):
                    continue
                try:
                    actual = path.resolve(strict=True)
                    if not actual.is_file():
                        continue
                    if actual not in seen:
                        progress.add()
                    seen.add(actual)
                    names.setdefault(name, set()).add(actual)
                    stems.setdefault(path.stem, set()).add(actual)
                except OSError as error:
                    if len(diagnostics) < 20:
                        diagnostics.append(f"{path}: {error}")
    return ReferenceIndex(
        {k: tuple(sorted(v)) for k, v in names.items()},
        {k: tuple(sorted(v)) for k, v in stems.items()},
        tuple(diagnostics),
    )


def resolve(
    source: Path,
    column: str,
    value: str,
    settings: ReferenceSettings,
    index: ReferenceIndex | None,
) -> Resolution:
    mapping = next(
        (m for m in settings.mappings if (m.column, m.value) == (column, value)), None
    )
    candidate = Path(mapping.path if mapping else value).expanduser()
    exact = candidate if candidate.is_absolute() else source.parent / candidate
    try:
        if exact.is_file():
            stat = exact.stat()
            return Resolution(
                value, AssetIdentity(exact.resolve(), stat.st_size, stat.st_mtime_ns)
            )
    except OSError as error:
        return Resolution(value, message=f"Reference unreadable: {error}")
    if mapping is not None:
        return Resolution(
            value, message=f"Mapped file missing: {exact}. Choose another file."
        )
    if index is None:
        return Resolution(
            value, message="Exact path missing; nearby discovery is still running."
        )
    choices = index.names.get(candidate.name, ()) or index.stems.get(candidate.stem, ())
    if len(choices) > 1:
        return Resolution(
            value,
            candidates=choices,
            message="Ambiguous reference: choose a file explicitly.",
        )
    if not choices:
        return Resolution(
            value,
            message="Reference missing. Edit roots/filters or choose a file and retry.",
        )
    try:
        stat = choices[0].stat()
        return Resolution(
            value, AssetIdentity(choices[0], stat.st_size, stat.st_mtime_ns)
        )
    except OSError as error:
        return Resolution(
            value, message=f"Indexed file missing/unreadable: {error}. Retry discovery."
        )
