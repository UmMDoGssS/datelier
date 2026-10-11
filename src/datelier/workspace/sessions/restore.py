"""Independent source recovery while preserving usable restored file recipes."""

from dataclasses import dataclass, replace
from pathlib import Path

from datelier.core.column_roles import TEXT_EXTENSIONS
from datelier.inspection.arrays import ArrayCatalog
from datelier.inspection.table import prepare_inspection
from datelier.io.importing import load_file
from datelier.io.objects import object_record_view
from datelier.io.types import ArrayOptions, ImportResult, MediaOptions, ObjectOptions
from datelier.pipeline import Pipeline
from datelier.workspace.sessions.storage import read_session_with_notice
from datelier.workspace.sessions.types import SessionFile, SessionWorkspace
from datelier.workspace.single import Workspace
from datelier.workspace.single.arrays import defer_array_view
from datelier.workspace.single.restore import (
    RestoredWorkspace,
    SourceIssue,
    restore_recipe,
)
from datelier.workspace.single.storage import reference_source


@dataclass(frozen=True)
class SourceRecovery:
    file_id: str
    relink: Path | None = None
    accept_changed: bool = False
    prepare_records: bool = False


@dataclass(frozen=True)
class RestoredSessionFile:
    file: SessionFile
    restored: RestoredWorkspace | None = None
    message: str = ""
    changed: bool = False
    record_views: tuple[RestoredSessionFile, ...] = ()
    deferred: bool = False
    array_catalog: ArrayCatalog | None = None


@dataclass(frozen=True)
class RestoredSession:
    workspace: SessionWorkspace
    files: tuple[RestoredSessionFile, ...]
    path: Path
    notice: str = ""


def restore_session_file(
    file: SessionFile,
    recovery: SourceRecovery | None = None,
    *,
    source_import: ImportResult | None = None,
) -> RestoredSessionFile:
    file.validate()
    if recovery is not None and recovery.file_id != file.identity:
        raise ValueError("Recovery belongs to another file tab")
    relink = recovery.relink if recovery is not None else None
    accept = recovery is not None and recovery.accept_changed
    try:
        recipe = file.recipe
        if (
            recipe is not None
            and isinstance(recipe.options, ArrayOptions)
            and recipe.options.mapping is not None
            and not (recovery is not None and recovery.prepare_records)
        ):
            deferred = defer_array_view(
                file, relink=relink, accept_changed=accept, source_import=source_import
            )
            views = tuple(
                restore_session_file(
                    view,
                    SourceRecovery(view.identity, relink, accept),
                    source_import=deferred.imported,
                )
                for view in file.record_views
            )
            updated = replace(
                deferred.file, record_views=tuple(view.file for view in views)
            )
            return RestoredSessionFile(
                updated,
                message="Saved mapping restored. Prepare records explicitly "
                "to load scalar fields and replay history.",
                changed=deferred.changed,
                record_views=views,
                deferred=True,
                array_catalog=deferred.catalog,
            )
        if recipe is not None:
            prepared: ImportResult | None = None
            if (
                source_import is not None
                and source_import.object_root is not None
                and isinstance(recipe.options, ObjectOptions)
            ):
                prepared = object_record_view(
                    source_import.object_root,
                    source_import.dataset.source,
                    recipe.options,
                )
            restored = restore_recipe(
                recipe, relink=relink, accept_changed=accept, imported_override=prepared
            )
        elif file.draft is not None:
            draft = file.draft
            imported = load_file(
                relink or Path(draft.path), draft.options, format=draft.format
            )
            recipe = Workspace(
                reference_source(imported.dataset.source),
                imported.format,
                imported.options,
            )
            pipeline = Pipeline.start(imported.dataset)
            restored = RestoredWorkspace(recipe, pipeline, prepare_inspection(imported))
        else:
            return RestoredSessionFile(file)
        changed = (
            file.recipe is not None
            and file.recipe.source.sha256 != restored.workspace.source.sha256
        )
        ids = restored.inspection.dataset.row_ids
        options = file.recipe.options if file.recipe is not None else None
        counted_members = (
            {member for member, _ in options.line_counts}
            if isinstance(options, MediaOptions)
            else set()
        )
        stable_manifest = isinstance(options, MediaOptions) and (
            options.manifest is None
            and bool(options.line_counts)
            or options.manifest is not None
            and (
                not options.text_lines
                or all(
                    not member.lower().endswith(TEXT_EXTENSIONS)
                    or member in counted_members
                    for member in options.manifest
                )
            )
        )
        selection = (
            ()
            if changed and not stable_manifest
            else tuple(
                int(row) for row in ids.filter(ids.is_in(file.selection)).to_list()
            )
        )
        message = (
            "Selection adjusted to the available source rows."
            if set(selection) != set(file.selection)
            else ""
        )
        updated = replace(
            file, recipe=restored.workspace, draft=None, selection=selection
        )
        views = tuple(
            restore_session_file(
                replace(
                    view,
                    recipe=replace(
                        view.recipe,
                        source=replace(
                            view.recipe.source, path=restored.workspace.source.path
                        ),
                    ),
                )
                if view.recipe is not None
                else view,
                SourceRecovery(view.identity, relink, accept),
                source_import=restored.inspection.imported,
            )
            for view in file.record_views
        )
        updated = replace(updated, record_views=tuple(view.file for view in views))
        return RestoredSessionFile(updated, restored, message, record_views=views)
    except SourceIssue as error:
        return RestoredSessionFile(file, message=str(error), changed=error.changed)
    except Exception as error:
        # Library/parser failures stay local to this source. The finite recipe
        # codec and session topology are validated before importing any file.
        return RestoredSessionFile(
            file,
            message=(
                f"Source could not reopen: {error}. "
                "Choose a replacement source or retry."
            ),
        )


def restore_session_workspace(
    path: Path, *, recoveries: tuple[SourceRecovery, ...] = ()
) -> RestoredSession:
    path = path.expanduser().resolve()
    session, notice = read_session_with_notice(path)
    identities = {file.identity for file in session.files}
    mapped = {recovery.file_id: recovery for recovery in recoveries}
    if len(mapped) != len(recoveries) or not set(mapped) <= identities:
        raise ValueError("Source recovery must identify distinct saved file tabs")
    files = tuple(
        restore_session_file(file, mapped.get(file.identity)) for file in session.files
    )
    return RestoredSession(
        replace(session, files=tuple(result.file for result in files)),
        files,
        path,
        notice,
    )
