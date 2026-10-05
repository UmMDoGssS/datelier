"""Native editor tabs above the shared dockspace."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.io.loading import LoadPhase


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
            editor.reorder(order)
        imgui.end_tab_bar()
        for identity in closed:
            editor.close_tab(identity)
            self.pixels.pop(identity, None)
        if create:
            editor.new_tab()
