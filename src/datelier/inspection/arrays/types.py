"""Array source metadata without decoded payloads or authoritative table copies."""

from dataclasses import dataclass

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

    def member(self, name: str) -> ArrayMember:
        member = next((m for m in self.members if m.name == name), None)
        if member is None:
            raise ValueError(f"Array member {name!r} is unavailable")
        return member
