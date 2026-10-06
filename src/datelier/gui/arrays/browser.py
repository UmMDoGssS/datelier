"""Route source slice controls and mapped-record inspection."""

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.editor_session import EditorSession


def show_array_browser(editor: EditorSession) -> None:
    owner = editor.active
    view = owner.record_views.active(owner)
    recipe = view.deferred.file.recipe if view.deferred is not None else None
    options = (
        view.loader.active.imported.options
        if view.loader.active is not None
        else recipe.options
        if recipe is not None
        else None
    )
    imgui.push_id(view.identity)
    _show_array_view(editor, options)
    imgui.pop_id()


def _show_array_view(editor: EditorSession, options: object) -> None:
    owner = editor.active
    view = owner.record_views.active(owner)
    if isinstance(options, ArrayOptions) and options.mapping is not None:
        if imgui.button("Browse source arrays"):
            owner.record_views.active_id = None
        imgui.same_line()
        if imgui.button("Edit record mapping"):
            owner.array_mapping.edit(options.mapping)
            owner.record_views.active_id = None
        if view.deferred is not None:
            imgui.text_wrapped(view.deferred.message)
        else:
            view.array_records.show(view)
    else:
        owner.array_mapping.show(owner)
        if not owner.array_mapping.opened:
            owner.array_view.show(owner)


def show_deferred_records(editor: EditorSession, identity: str) -> bool:
    view = next(file for file in editor.file_sessions if file.identity == identity)
    if view.deferred is None:
        return False
    imgui.text_wrapped(view.deferred.message)
    imgui.begin_disabled(editor.workspace_jobs.busy)
    if imgui.button("Prepare saved array records"):
        editor.prepare_records(identity)
    imgui.end_disabled()
    if editor.workspace_jobs.recovering(identity):
        imgui.text_wrapped(editor.workspace_jobs.message)
        if imgui.button("Abandon saved record preparation"):
            editor.workspace_jobs.abandon()
            editor.workspace_jobs.message = (
                "Result abandoned; active supporting reads may finish."
            )
    return True
