"""Open media as metadata record collections; text lines are an explicit import."""

from dataclasses import replace
from pathlib import Path

import polars as pl

from datelier.core.column_roles import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
    ColumnRole,
)
from datelier.core.dataset import Dataset, SourceReference
from datelier.io.media_manifest import directory_signature, media_members
from datelier.io.types import ImportFailure, ImportFormat, ImportResult, MediaOptions


def load_media(path: Path, options: MediaOptions | None = None) -> ImportResult:
    path = path.expanduser().resolve()
    settings = options or MediaOptions()
    try:
        folder = path.is_dir()
        before = (
            directory_signature(path)
            if folder
            else (path.stat().st_size, path.stat().st_mtime_ns, "")
        )
        members = (
            settings.manifest
            if folder and settings.manifest is not None
            else media_members(path, settings.recursive)
            if folder
            else (path.name,)
        )
        rows: list[tuple[str, str, str, int | None, int | None, str | None]] = []
        diagnostics: list[str] = []
        line_counts = dict(settings.line_counts)
        for member in members:
            target = path / member if folder else path
            suffix = target.suffix.lower()
            kind = (
                "Image"
                if suffix in IMAGE_EXTENSIONS
                else "Audio"
                if suffix in AUDIO_EXTENSIONS
                else "Text"
            )
            try:
                size = target.stat().st_size
            except OSError as error:
                diagnostics.append(
                    f"Missing/unreadable manifest member: {member}: {error}"
                )
                if settings.text_lines and suffix in TEXT_EXTENSIONS:
                    for number in range(1, line_counts.get(member, 1) + 1):
                        rows.append((str(target), member, kind, None, number, None))
                else:
                    rows.append((str(target), member, kind, None, None, None))
                continue
            if settings.text_lines and suffix in TEXT_EXTENSIONS:
                expected = line_counts.get(member)
                actual = 0
                with target.open(encoding="utf8") as stream:
                    for number, line in enumerate(stream, 1):
                        actual = number
                        if expected is not None and number > expected:
                            continue
                        rows.append(
                            (
                                str(target),
                                member,
                                kind,
                                size,
                                number,
                                line.removesuffix("\n").removesuffix("\r"),
                            )
                        )
                line_counts[member] = actual if expected is None else expected
                if expected is not None and expected != actual:
                    diagnostics.append(
                        f"{member}: retained {expected} saved line records; "
                        f"current file has {actual}. Refresh the import manifest "
                        "to use current membership."
                    )
                    for number in range(actual + 1, expected + 1):
                        rows.append((str(target), member, kind, size, number, None))
            else:
                rows.append((str(target), member, kind, size, None, None))
        after = (
            directory_signature(path)
            if folder
            else (path.stat().st_size, path.stat().st_mtime_ns, "")
        )
        if before != after:
            raise ImportFailure(
                path, "Source changed while building media records; retry."
            )
        table = pl.DataFrame(
            rows,
            schema={
                "path": pl.String,
                "member": pl.String,
                "kind": pl.String,
                "size_bytes": pl.UInt64,
                "line": pl.UInt64,
                "text": pl.String,
            },
            orient="row",
        )
        dataset = Dataset.from_source(table, SourceReference(path, after[0], after[1]))
        path_role = (
            ColumnRole.PATH
            if folder
            else ColumnRole.IMAGE
            if path.suffix.lower() in IMAGE_EXTENSIONS
            else ColumnRole.AUDIO
            if path.suffix.lower() in AUDIO_EXTENSIONS
            else ColumnRole.EXTERNAL_TEXT
        )
        # Collection paths are references even when a mixed/empty manifest has no
        # majority extension evidence. This belongs to the source adapter.
        roles = tuple(
            replace(info, inferred=path_role, reason="Media source record reference.")
            if info.name == "path"
            else replace(
                info, inferred=ColumnRole.TEXT, reason="Original text-line content."
            )
            if info.name == "text"
            else info
            for info in dataset.roles or ()
        )
        dataset = replace(dataset, roles=roles)
        diagnostics.append(
            "One record per text line."
            if settings.text_lines
            else "One record per file; payloads are decoded lazily."
        )
        return ImportResult(
            dataset,
            replace(
                settings,
                manifest=members if folder else None,
                line_counts=tuple(line_counts.items()),
            ),
            tuple(diagnostics),
            ImportFormat.MEDIA,
        )
    except ImportFailure:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise ImportFailure(
            path,
            f"Could not open media records: {error}. Retry or choose another source.",
        ) from error
