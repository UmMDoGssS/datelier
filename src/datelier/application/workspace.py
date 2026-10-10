"""Capture semantic recipes and install ready/recoverable sources without GUI state."""

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from datelier.analysis.types import Algorithm
from datelier.core.dataset import SourceReference
from datelier.io.loading import LoadPhase, LoadStatus
from datelier.workspace.session_jobs import SessionSnapshot
from datelier.workspace.session_restore import RestoredSessionFile
from datelier.workspace.session_types import SessionFile
from datelier.workspace.types import Workspace, WorkspaceSource, WorkspaceViews

if TYPE_CHECKING:
    from datelier.application.editor import EditorController
    from datelier.application.file import FileController


def capture_views(file: FileController) -> WorkspaceViews:
    return replace(
        file.views,
        profile_selection=file.profiles.selected,
        profile_mode=file.profiles.mode,
        profile_height=file.profiles.height,
        profile_text=file.profiles.text,
        coordinate_source=file.analysis.source,
        scatter_dimensions=file.plots.scatter_dimensions,
        color_source=file.plots.color_source,
        column_start=file.table.column_start,
        target_row=file.table.target_row,
        references=file.references.settings,
        inspect=file.records.settings,
        array_slice=file.arrays.settings,
        array_retention_bytes=file.arrays.store.limit,
        checkpoint_slice=file.checkpoints.settings,
        checkpoint_retention_bytes=file.checkpoints.store.limit,
        array_height=file.array_source.height,
        array_record_height=file.array_record_source.height,
        array_record_slice=file.array_records.jobs.settings,
        checkpoint_height=file.tensor_source.height,
        array_member_mode=file.array_source.member_mode,
        checkpoint_member_mode=file.tensor_source.member_mode,
        text=file.text.jobs.settings,
        text_height=file.text.original_height,
        token_height=file.text.token_height,
        image=file.images.settings,
        audio=file.audio.settings,
    )


def capture_file(
    file: FileController, sources: list[tuple[str, SourceReference]]
) -> SessionFile:
    if (
        file.editor.busy
        or file.loader.status.phase == LoadPhase.LOADING
        or file.exporter.busy
        or file.record_views.pending
    ):
        raise ValueError("Wait for file imports, edits and writes before saving")
    active, pipeline = file.inspection, file.editor.pipeline
    if active and pipeline:
        source = pipeline.source.source
        sources.append((file.identity, source))
        recipe = Workspace(
            WorkspaceSource(
                str(source.path), source.size_bytes, source.modified_ns, "0" * 64
            ),
            active.imported.format,
            active.imported.options,
            pipeline.history,
            pipeline.cursor,
            tuple(file.analysis.controls.request(a) for a in Algorithm),
            replace(file.plots.settings(), clusters=None),
            capture_views(file),
        )
        views = file.record_views
        return SessionFile(
            file.identity,
            recipe,
            selection=tuple(sorted(file.selection.row_ids)),
            name=file.view_name,
            record_views=tuple(capture_file(v, sources) for v in views.files),
            active_view=views.active_id,
            object_path=views.path,
            object_focus=views.focus_path,
            object_expanded=tuple(sorted(views.expanded, key=repr)),
        )
    if file.recovery:
        return file.recovery.file
    return SessionFile(file.identity, draft=file.draft, name=file.view_name)


def capture_session(
    editor: EditorController,
    layout: str = "",
    hidden: tuple[str, ...] = (),
    customized: bool = False,
) -> SessionSnapshot:
    sources: list[tuple[str, SourceReference]] = []
    files = tuple(capture_file(file, sources) for file in editor.files)
    original = editor.saved_session
    workspace = replace(
        original,
        files=files,
        active_id=editor.active_id,
        layout=layout,
        hidden_windows=hidden,
        custom_layout=customized,
        canvas_mode="Compare files" if editor.navigation.comparing else "Inspection",
        context_tab=editor.navigation.context_tab,
    )
    return SessionSnapshot(workspace, tuple(sources))


def install_file(file: FileController, result: RestoredSessionFile) -> None:
    from datelier.application.file import FileController

    file.view_name = result.file.name
    file.recovery = None
    file.record_views.clear()
    if result.restored:
        file.install(result.restored)
        file.selection.choose(
            result.restored.inspection.dataset.revision, result.file.selection
        )
        views = file.record_views
        views.path, views.focus_path = result.file.object_path, result.file.object_focus
        views.expanded = set(result.file.object_expanded)
        for child in result.record_views:
            view = FileController(
                views.executor,
                identity=child.file.identity,
                array_store=file.arrays.store,
                playback=views.playback,
            )
            install_file(view, child)
            views.files.append(view)
        views.active_id = result.file.active_view
    elif result.message:
        file.recovery = result
        recipe, draft = result.file.recipe, result.file.draft
        source = recipe.source.path if recipe else draft.path if draft else ""
        file.loader.status = LoadStatus(LoadPhase.FAILED, Path(source), result.message)
        if result.deferred and result.array_catalog:
            file.arrays.catalog = result.array_catalog
            if recipe:
                file.views = recipe.views
