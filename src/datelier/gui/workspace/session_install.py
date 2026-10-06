"""Install ready, deferred and recoverable file recipes without loading payloads."""

from pathlib import Path
from typing import TYPE_CHECKING

from datelier.io.loading import LoadPhase, LoadStatus
from datelier.workspace.session_restore import RestoredSessionFile

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


def install_session_file(session: FileSession, result: RestoredSessionFile) -> None:
    from datelier.gui.file_session import FileSession

    session.view_name = result.file.name
    session.panel_scroll = {name: (x, y) for name, x, y in result.file.panel_scroll}
    session.deferred = None
    session.recovery = None
    if result.restored is not None:
        adjusted = session.install_restored(result.restored)
        session.selection.choose(
            result.restored.inspection.dataset.revision, result.file.selection
        )
        message = result.message
        if adjusted:
            message += " Saved view settings were adjusted to the available columns."
        if message:
            session.loader.status = LoadStatus(
                LoadPhase.READY, session.loader.status.path, message.strip()
            )
        views = session.record_views
        views.path, views.focus_path = result.file.object_path, result.file.object_focus
        views.expanded = set(result.file.object_expanded)
        # Bind before borrowing: the owner keeps one cache for all named views.
        imported = result.restored.inspection.imported
        if imported.array_catalog is not None:
            session.arrays.bind(
                imported.array_catalog, result.restored.inspection.dataset.revision
            )
        for child in result.record_views:
            view = FileSession.create(
                session.preferences,
                executor=views.executor,
                array_store=session.arrays.store
                if child.array_catalog is not None
                else None,
            )
            view.identity = child.file.identity
            view.install_session_file(child)
            views.files.append(view)
        views.active_id = result.file.active_view
    elif result.message:
        recipe, draft = result.file.recipe, result.file.draft
        if recipe is not None:
            session.controls.path = recipe.source.path
            session.controls.bind_settings(recipe.format, recipe.options)
        elif draft is not None:
            session.controls.path = draft.path
            session.controls.bind_settings(draft.format, draft.options)
        if result.deferred:
            assert recipe is not None and result.array_catalog is not None
            session.deferred = result
            session.arrays.catalog = result.array_catalog
            session.arrays.settings = (
                recipe.views.array_slice or session.arrays.settings
            )
            session.arrays.store.limit = recipe.views.array_retention_bytes
        else:
            session.recovery = result
        session.loader.status = LoadStatus(
            LoadPhase.READY if result.deferred else LoadPhase.FAILED,
            Path(session.controls.path),
            result.message,
        )
