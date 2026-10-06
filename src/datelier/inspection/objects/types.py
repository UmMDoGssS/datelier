"""Immutable object hierarchy with typed, lossless node navigation."""

from dataclasses import dataclass
from datetime import date, datetime, time

type NodeKey = str | int
type NodePath = tuple[NodeKey, ...]
type ObjectScalar = str | int | float | bool | date | datetime | time | None


@dataclass(frozen=True)
class ObjectChild:
    key: NodeKey
    node: ObjectNode


@dataclass(frozen=True)
class ObjectNode:
    kind: str
    value: ObjectScalar = None
    children: tuple[ObjectChild, ...] = ()

    @property
    def preview(self) -> str:
        if self.kind in ("object", "array"):
            return f"{len(self.children)} entries"
        text = repr(self.value)
        return text if len(text) <= 256 else text[:256] + "… (truncated)"

    def at(self, path: NodePath) -> ObjectNode:
        node = self
        for key in path:
            if node.kind == "array" and type(key) is int:
                if not 0 <= key < len(node.children):
                    raise ValueError(f"Array index {key} is unavailable")
                node = node.children[key].node
            elif node.kind == "object" and isinstance(key, str):
                child = next((c for c in node.children if c.key == key), None)
                if child is None:
                    raise ValueError(f"Object field {key!r} is unavailable")
                node = child.node
            else:
                raise ValueError(f"Cannot navigate {key!r} within {node.kind}")
        return node


def node_label(path: NodePath) -> str:
    return "$" + "".join(f"[{key!r}]" for key in path)
