"""Bounded, paged expandable trees rendered only from imported object nodes."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.gui.file_session import FileSession
from datelier.inspection.objects.types import NodePath, ObjectNode, node_label
from datelier.io.types import ImportFormat, ObjectOptions

CHILD_PAGE = 32
TREE_ROWS = 128


@dataclass
class ObjectBrowser:
    as_text: bool = False
    rendered: int = 0
    node_pixels: dict[NodePath, tuple[float, float]] = field(default_factory=dict)
    open_pixel: tuple[float, float] = (0, 0)
    focus_pixel: tuple[float, float] = (0, 0)

    def show(self, owner: FileSession) -> None:
        active = owner.loader.active
        if active is None:
            imgui.text_wrapped("Open a JSON or TOML source to browse its hierarchy.")
            return
        root = active.imported.object_root
        if root is None:
            imgui.text_wrapped(
                "Choose JSON / TOML object in import options to browse structured data."
            )
            if active.imported.format == ImportFormat.JSON and imgui.button(
                "Browse JSON source"
            ):
                owner.loader.request(
                    active.dataset.source.path,
                    ObjectOptions(),
                    format=ImportFormat.OBJECT,
                )
            return
        views = owner.record_views
        try:
            selected = root.at(views.path)
        except ValueError:
            views.path = ()
            selected = root
        imgui.text_wrapped(node_label(views.path))
        if imgui.button("Root"):
            views.path = ()
            views.focus_path = ()
        imgui.same_line()
        if imgui.button("Parent") and views.path:
            views.path = views.path[:-1]
            views.focus_path = views.path
        imgui.same_line()
        if imgui.button("Focus selected node"):
            views.focus_path = views.path
            views.expanded = {views.path}
            views.offsets.clear()
        self.focus_pixel = _pixel()
        imgui.text_wrapped(f"{selected.kind}: {selected.preview}")
        object_records = isinstance(active.imported.options, ObjectOptions)
        if object_records:
            _, self.as_text = imgui.checkbox(
                "Read record columns as text", self.as_text
            )
        if selected.kind == "array" and object_records:
            if imgui.button("Open records as table view"):
                try:
                    views.open(owner, views.path, as_text=self.as_text)
                    views.message = "Preparing an independent table view…"
                except ValueError as error:
                    views.message = str(error)
            self.open_pixel = _pixel()
        if views.message:
            imgui.text_wrapped(views.message)
        self.rendered = 0
        self.node_pixels.clear()
        try:
            focused = root.at(views.focus_path)
        except ValueError:
            views.focus_path = ()
            focused = root
        self._tree(owner, focused, views.focus_path, node_label(views.focus_path))
        if self.rendered >= TREE_ROWS:
            imgui.text_wrapped(
                "Tree display limit reached. Focus a selected node "
                "to inspect its children."
            )

    def _tree(
        self, owner: FileSession, node: ObjectNode, path: NodePath, label: str
    ) -> None:
        if self.rendered >= TREE_ROWS:
            return
        self.rendered += 1
        views = owner.record_views
        imgui.push_id(node_label(path))
        flags = (
            imgui.TreeNodeFlags_.open_on_arrow | imgui.TreeNodeFlags_.span_avail_width
        )
        if path == views.path:
            flags |= imgui.TreeNodeFlags_.selected
        if not node.children:
            flags |= imgui.TreeNodeFlags_.leaf
        imgui.set_next_item_open(path in views.expanded)
        opened = imgui.tree_node_ex(f"{label} · {node.kind} · {node.preview}", flags)
        self.node_pixels[path] = _pixel()
        if imgui.is_item_clicked() and not imgui.is_item_toggled_open():
            views.path = path
        if opened:
            if node.children:
                views.expanded.add(path)
            offset = min(views.offsets.get(path, 0), max(0, len(node.children) - 1))
            if len(node.children) > CHILD_PAGE:
                end = min(offset + CHILD_PAGE, len(node.children))
                imgui.text(f"Entries {offset + 1}–{end} of {len(node.children)}")
                if imgui.small_button("Previous entries"):
                    views.offsets[path] = max(0, offset - CHILD_PAGE)
                imgui.same_line()
                if imgui.small_button("Next entries"):
                    views.offsets[path] = min(
                        max(0, len(node.children) - CHILD_PAGE), offset + CHILD_PAGE
                    )
            for child in node.children[offset : offset + CHILD_PAGE]:
                self._tree(owner, child.node, (*path, child.key), repr(child.key))
            imgui.tree_pop()
        else:
            views.expanded.discard(path)
        imgui.pop_id()


def show_view_selector(owner: FileSession) -> None:
    views = owner.record_views
    if not views.files:
        return
    names = ["Source", *(file.view_name for file in views.files)]
    identities = [None, *(file.identity for file in views.files)]
    index = identities.index(views.active_id) if views.active_id in identities else 0
    changed, index = imgui.combo("Record view", index, names)
    if changed:
        views.active_id = identities[index]
    if views.active_id is not None:
        imgui.same_line()
        if imgui.small_button("Close view"):
            views.close_view(views.active_id)


def _pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
