"""Immutable editor snapshots; source fingerprinting belongs to workers."""

from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.analysis.types import Algorithm
from datelier.core.dataset import SourceReference
from datelier.gui.workspace.state import capture_views
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFailure
from datelier.workspace.session_jobs import SessionSnapshot
from datelier.workspace.session_types import SessionFile, SessionWorkspace, SourceDraft
from datelier.workspace.types import Workspace, WorkspaceSource

if TYPE_CHECKING:
    from datelier.gui.editor_session import EditorSession
    from datelier.gui.file_session import FileSession


def capture_file(
    file: FileSession, sources: list[tuple[str, SourceReference]]
) -> SessionFile:
    if (
        file.editor.busy
        or file.loader.status.phase == LoadPhase.LOADING
        or file.workspace.jobs.busy
        or file.exporter.busy
        or file.record_views.pending
    ):
        raise ValueError("Wait for file imports, edits or writes before saving")
    active, pipeline = file.loader.active, file.editor.pipeline
    if active is not None and pipeline is not None:
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
            tuple(file.analysis.controls.request(algorithm) for algorithm in Algorithm),
            replace(file.plots.settings(), clusters=None),
            capture_views(file),
        )
        views = file.record_views
        return SessionFile(
            file.identity,
            recipe,
            selection=tuple(sorted(file.selection.row_ids)),
            panel_scroll=tuple(
                (name, x, y) for name, (x, y) in file.panel_scroll.items()
            ),
            name=file.view_name,
            record_views=tuple(capture_file(view, sources) for view in views.files),
            active_view=views.active_id,
            object_path=views.path,
            object_focus=views.focus_path,
            object_expanded=tuple(sorted(views.expanded, key=repr)),
        )
    if file.recovery is not None:
        return file.recovery.file
    if file.deferred is not None:
        return replace(
            file.deferred.file,
            panel_scroll=tuple(
                (name, x, y) for name, (x, y) in file.panel_scroll.items()
            ),
        )
    if file.controls.path.strip():
        try:
            format = file.controls.selected_format()
            draft = SourceDraft(
                file.controls.path, format, file.controls.options(format)
            )
        except (ImportFailure, ValueError) as error:
            raise ValueError(
                f"Fix import settings in {file.controls.path}: {error}"
            ) from error
        return SessionFile(file.identity, draft=draft, name=file.view_name)
    return SessionFile(file.identity, name=file.view_name)


def capture_session(
    editor: EditorSession, layout: str = "", hidden: tuple[str, ...] = ()
) -> SessionSnapshot:
    sources: list[tuple[str, SourceReference]] = []
    files = tuple(capture_file(file, sources) for file in editor.files)
    return SessionSnapshot(
        SessionWorkspace(
            files,
            editor.active_id,
            editor.comparisons,
            layout,
            hidden,
            text_comparisons=editor.text_comparisons,
            image_comparisons=editor.image_comparisons,
            image_comparison_index=min(
                editor.image_comparison_index, max(0, len(editor.image_comparisons) - 1)
            ),
            image_comparison_view=editor.image_comparison_view,
            comparison_tab=editor.comparison_tab,
            audio_comparisons=editor.audio_comparisons,
            audio_comparison_index=min(
                editor.audio_comparison_index, max(0, len(editor.audio_comparisons) - 1)
            ),
            audio_comparison_view=editor.audio_comparison_view,
            text_comparison_index=min(
                editor.text_comparison_index, max(0, len(editor.text_comparisons) - 1)
            ),
        ),
        tuple(sources),
    )
