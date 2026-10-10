"""Atomic whole-session storage with version-one migration and portable paths."""

import json
import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_types import SessionFile, SessionWorkspace
from datelier.workspace.storage import (
    MAX_WORKSPACE_BYTES,
    atomic_write,
    protect_sources,
    read_recipe,
)
from datelier.workspace.types import Workspace


def map_paths(file: SessionFile, convert: Callable[[str], str]) -> SessionFile:
    recipe, draft = file.recipe, file.draft
    if recipe is not None:
        recipe = replace(
            recipe, source=replace(recipe.source, path=convert(recipe.source.path))
        )
    if draft is not None:
        draft = replace(draft, path=convert(draft.path))
    return replace(
        file,
        recipe=recipe,
        draft=draft,
        record_views=tuple(map_paths(view, convert) for view in file.record_views),
    )


def source_paths(session: SessionWorkspace) -> tuple[Path, ...]:
    sources: list[Path] = []
    for file in session.files:
        if file.recipe is not None:
            sources.append(Path(file.recipe.source.path))
        elif file.draft is not None:
            sources.append(Path(file.draft.path))
    return tuple(sources)


def save_session_workspace(
    path: Path, session: SessionWorkspace, *, sources: tuple[Path, ...] = ()
) -> None:
    path = path.expanduser().resolve()
    session.validate()
    protect_sources(path, (*source_paths(session), *sources))
    relative = replace(
        session,
        files=tuple(
            map_paths(
                file,
                lambda value: os.path.relpath(
                    Path(value).expanduser().resolve(), path.parent
                ),
            )
            for file in session.files
        ),
    )
    content = json.dumps(encode(relative), indent=2, allow_nan=False)
    if len(content.encode("utf8")) > MAX_WORKSPACE_BYTES:
        raise ValueError("Workspace exceeds the 2 MiB recipe limit")
    atomic_write(path, content + "\n")


def read_session_workspace(path: Path) -> SessionWorkspace:
    return read_session_with_notice(path)[0]


def read_session_with_notice(path: Path) -> tuple[SessionWorkspace, str]:
    path = path.expanduser().resolve()
    raw = read_recipe(path)
    notice = ""
    if isinstance(raw, dict) and raw.get("kind") == "Workspace":
        notice = (
            "Workspace updated to the current workbench; "
            "recipes and view settings preserved."
        )
        legacy = decode_record(Workspace, raw)
        legacy.validate()
        session = SessionWorkspace(
            (SessionFile("legacy-source", legacy),), "legacy-source"
        )
    else:
        if (
            isinstance(raw, dict)
            and type(raw.get("version", 2)) is int
            and raw.get("version", 2) == 2
        ):
            raw = dict(raw)
            raw.update(
                version=3,
                layout_version=2,
                layout="",
                hidden_windows=[],
                custom_layout=False,
            )
            notice = (
                "Workbench layout updated; recipes, settings and selections preserved."
            )
        session = decode_record(SessionWorkspace, raw)
    session.validate()
    resolved = replace(
        session,
        files=tuple(
            map_paths(file, lambda value: str((path.parent / value).resolve()))
            for file in session.files
        ),
    )

    return resolved, notice
