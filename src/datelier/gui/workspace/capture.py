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


def capture_session(
    editor: EditorSession, layout: str = "", hidden: tuple[str, ...] = ()
) -> SessionSnapshot:
    files: list[SessionFile] = []
    sources: list[tuple[str, SourceReference]] = []
    for file in editor.files:
        if (
            file.editor.busy
            or file.loader.status.phase == LoadPhase.LOADING
            or file.workspace.jobs.busy
            or file.exporter.busy
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
                tuple(
                    file.analysis.controls.request(algorithm) for algorithm in Algorithm
                ),
                replace(file.plots.settings(), clusters=None),
                capture_views(file),
            )
            files.append(
                SessionFile(
                    file.identity,
                    recipe,
                    selection=tuple(sorted(file.selection.row_ids)),
                    panel_scroll=tuple(
                        (name, x, y) for name, (x, y) in file.panel_scroll.items()
                    ),
                )
            )
        elif file.recovery is not None:
            files.append(file.recovery.file)
        elif file.controls.path.strip():
            try:
                format = file.controls.selected_format()
                draft = SourceDraft(
                    file.controls.path, format, file.controls.options(format)
                )
            except (ImportFailure, ValueError) as error:
                raise ValueError(
                    f"Fix import settings in {file.controls.path}: {error}"
                ) from error
            files.append(SessionFile(file.identity, draft=draft))
        else:
            files.append(SessionFile(file.identity))
    return SessionSnapshot(
        SessionWorkspace(
            tuple(files), editor.active_id, editor.comparisons, layout, hidden
        ),
        tuple(sources),
    )
