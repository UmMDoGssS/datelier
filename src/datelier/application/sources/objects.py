"""Bounded object navigation prepared before drawing, without source reads."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from datelier.inspection.objects import NodePath, ObjectNode, node_label

if TYPE_CHECKING:
    from datelier.application.sessions.records import RecordViews


@dataclass(frozen=True)
class ObjectEntry:
    path: NodePath
    label: str
    kind: str
    preview: str
    container: bool


class ObjectController:
    def __init__(self, navigation: RecordViews) -> None:
        self.navigation = navigation
        self.root: ObjectNode | None = None
        self.entries: tuple[ObjectEntry, ...] = ()
        self.selected: ObjectEntry | None = None
        self.detail = ""
        self.offset = 0
        self.length = 0
        self.as_text = False
        self._stamp: tuple[ObjectNode, NodePath, int] | None = None

    def sync(self, root: ObjectNode | None) -> None:
        stamp = (root, self.navigation.path, self.offset) if root else None
        # Identity avoids comparing whole imported trees every frame.
        if (
            self._stamp
            and stamp
            and self._stamp[0] is root
            and self._stamp[1:] == stamp[1:]
        ):
            return
        self.root = root
        self._stamp = stamp
        self.entries = ()
        self.selected = None
        self.detail = ""
        self.length = 0
        if root is None:
            return
        try:
            node = root.at(self.navigation.path)
        except ValueError:
            self.navigation.path = ()
            node = root
        path = self.navigation.path
        self.selected = ObjectEntry(
            path, node_label(path), node.kind, node.preview, bool(node.children)
        )
        self.entries = tuple(
            ObjectEntry(
                (*path, child.key),
                repr(child.key),
                child.node.kind,
                child.node.preview,
                bool(child.node.children),
            )
            for child in node.children
        )
        value = node.value
        if isinstance(value, str):
            self.length = len(value)
            self.offset = min(self.offset, max(0, self.length - 1))
            self.detail = value[self.offset : self.offset + 4096]
        else:
            self.detail = node.preview

    def choose(self, path: NodePath) -> None:
        if self.root is None:
            return
        self.root.at(path)
        self.navigation.path = path
        self.offset = 0

    def page(self, delta: int) -> None:
        self.offset = max(
            0, min(max(0, self.length - 4096), self.offset + delta * 4096)
        )
