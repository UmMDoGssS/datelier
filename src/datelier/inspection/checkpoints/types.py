"""Immutable checkpoint hierarchy and tensor locators, independent of PyTorch."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from datelier.core.dataset import SourceReference
from datelier.inspection.objects.types import NodePath, ObjectNode


@dataclass(frozen=True)
class TensorInfo:
    path: NodePath
    name: str
    shape: tuple[int, ...]
    dtype: str
    layout: str
    strides: tuple[int, ...]
    storage_offset: int
    raw_bytes: int
    diagnostic: str = ""


@dataclass(frozen=True)
class CheckpointCatalog:
    source: SourceReference
    root: ObjectNode
    tensors: tuple[TensorInfo, ...]
    mapped: bool
    indices: Mapping[str, TensorInfo] = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "indices", MappingProxyType({t.name: t for t in self.tensors})
        )

    def tensor(self, name: str) -> TensorInfo:
        result = self.indices.get(name)
        if result is None:
            raise ValueError("Saved tensor locator is unavailable in this checkpoint")
        return result
