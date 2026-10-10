"""Native editor tabs above the shared dockspace."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.io.loading import LoadPhase
from datelier.pipeline.editing import HistoryAction


def tab_label(file: FileSession) -> str:
    source = file.loader.status.path
    if file.loader.active is not None:
        source = file.loader.active.dataset.source.path
    title = source.name if source is not None else "Welcome"
    if file.loader.status.phase == LoadPhase.LOADING:
        title += " · loading"
    elif file.loader.status.phase == LoadPhase.FAILED:
        title += " · failed"
    elif file.analysis.jobs.busy:
        title += " · analyzing"
    # Stable IDs preserve native tab order when labels/status change.
    return f"{title}###{file.identity}"


@dataclass
class EditorTabs:
    pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    native_order: tuple[str, ...] = ()
    new_pixel: tuple[float, float] = (0, 0)

    def show(self, editor: EditorSession) -> None:
        view = editor.active.record_views.active(editor.active)
        pipeline = view.editor.pipeline
        imgui.begin_disabled(
            view.editor.busy or view.loader.status.phase == LoadPhase.LOADING
        )
        imgui.begin_disabled(pipeline is None or not pipeline.can_undo)
        if imgui.button("Undo"):
            view.editor.request(HistoryAction.UNDO)
        imgui.end_disabled()
        imgui.same_line()
        imgui.begin_disabled(pipeline is None or not pipeline.can_redo)
        if imgui.button("Redo"):
            view.editor.request(HistoryAction.REDO)
        imgui.end_disabled()
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Context"):
            if (
                imgui.get_io().display_size.x < 1100
                and not editor.preferences.layout_customized
            ):
                editor.navigation.context_open = not editor.navigation.context_open
            else:
                from imgui_bundle import hello_imgui

                for (
                    window
                ) in hello_imgui.get_runner_params().docking_params.dockable_windows:
                    if window.label == "Context":
                        window.is_visible = not window.is_visible
        imgui.same_line()
        if imgui.button("Table"):
            from imgui_bundle import hello_imgui

            for (
                window
            ) in hello_imgui.get_runner_params().docking_params.dockable_windows:
                if window.label == "Table preview":
                    window.is_visible = not window.is_visible
        imgui.same_line()
        identities = {file.identity for file in editor.files}
        self.pixels = {
            key: value for key, value in self.pixels.items() if key in identities
        }
        flags = (
            imgui.TabBarFlags_.reorderable
            | imgui.TabBarFlags_.tab_list_popup_button
            | imgui.TabBarFlags_.fitting_policy_scroll
        )
        if not imgui.begin_tab_bar("Editor files", flags):
            return
        if editor.order_reset:
            native = imgui.internal.get_current_tab_bar()
            for identity in tuple(tab.id_ for tab in native.tabs):
                imgui.internal.tab_bar_remove_tab(native, identity)
            editor.order_reset = False
        closed: list[str] = []
        native_ids: dict[int, str] = {}
        requested = editor.focus_requested
        for file in tuple(editor.files):
            label = tab_label(file)
            native_ids[imgui.get_id(label)] = file.identity
            item_flags = (
                imgui.TabItemFlags_.set_selected
                if requested == file.identity
                else imgui.TabItemFlags_.none
            )
            selected, opened = imgui.begin_tab_item(label, True, item_flags)
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            self.pixels[file.identity] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            if imgui.is_item_hovered():
                source = file.loader.status.path
                imgui.set_tooltip(str(source) if source else "Open a file in this tab")
            if imgui.is_item_clicked():
                editor.navigation.activate_file()
                view = file.record_views.active(file)
                view.exploration.tab = view.exploration.active_tab
            if selected:
                editor.activate(file.identity, focus=False)
                imgui.end_tab_item()
            if opened is False:
                closed.append(file.identity)
        editor.focus_requested = None
        create = imgui.tab_item_button(
            "+ New Tab", imgui.TabItemFlags_.trailing | imgui.TabItemFlags_.no_reorder
        )
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.new_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        native = imgui.internal.get_current_tab_bar()
        order = tuple(
            native_ids[tab.id_] for tab in native.tabs if tab.id_ in native_ids
        )
        self.native_order = order
        if len(order) == len(editor.files):
            editor.reorder(order, native=True)
        imgui.end_tab_bar()
        for identity in closed:
            editor.close_tab(identity)
            self.pixels.pop(identity, None)
        if create:
            editor.new_tab()
