"""Immutable object hierarchy with typed, lossless node navigation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from types import MappingProxyType

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
    _fields: Mapping[NodeKey, ObjectNode] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_fields",
            MappingProxyType(
                {child.key: child.node for child in self.children}
                if self.kind == "object"
                else {}
            ),
        )

    @property
    def preview(self) -> str:
        if self.kind in ("object", "array"):
            return f"{len(self.children)} entries"
        value = self.value
        shortened = isinstance(value, str) and len(value) > 256
        text = repr(value[:256] if shortened else value)
        if shortened:
            return text + "… (truncated)"
        return text if len(text) <= 256 else text[:256] + "… (truncated)"

    def at(self, path: NodePath) -> ObjectNode:
        node = self
        for key in path:
            if node.kind == "array" and type(key) is int:
                if not 0 <= key < len(node.children):
                    raise ValueError(f"Array index {key} is unavailable")
                node = node.children[key].node
            elif node.kind == "object" and isinstance(key, str):
                child = node._fields.get(key)
                if child is None:
                    raise ValueError(f"Object field {key!r} is unavailable")
                node = child
            else:
                raise ValueError(f"Cannot navigate {key!r} within {node.kind}")
        return node


def node_label(path: NodePath) -> str:
    return "$" + "".join(f"[{key!r}]" for key in path)
