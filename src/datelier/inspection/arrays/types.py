"""Array source metadata without decoded payloads or authoritative table copies."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

from datelier.core.dataset import SourceReference


@dataclass(frozen=True)
class ArrayMember:
    name: str
    storage_name: str | None
    shape: tuple[int, ...] = ()
    dtype: np.dtype[np.generic] | None = None
    fortran_order: bool = False
    header_bytes: int = 0
    raw_bytes: int = 0
    stored_bytes: int = 0
    container_bytes: int = 0
    compressed: bool = False
    diagnostic: str = ""

    @property
    def usable(self) -> bool:
        return (
            self.dtype is not None and not self.dtype.hasobject and not self.diagnostic
        )


@dataclass(frozen=True)
class ArrayCatalog:
    source: SourceReference
    members: tuple[ArrayMember, ...]
    diagnostics: tuple[str, ...] = ()
    indices: Mapping[str, int] = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "indices",
            MappingProxyType({m.name: i for i, m in enumerate(self.members)}),
        )

    def member(self, name: str) -> ArrayMember:
        index = self.indices.get(name)
        if index is None:
            raise ValueError(f"Array member {name!r} is unavailable")
        return self.members[index]
