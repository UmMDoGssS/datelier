"""Exact array/tensor window controls persisted as finite recipes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SliceSettings:
    member: str = "$"
    axes: tuple[int, ...] = ()
    fixed: tuple[int, ...] = ()
    starts: tuple[int, ...] = ()
    counts: tuple[int, ...] = ()
    field: str | None = None
    component: str = "Magnitude"
    scalar: bool = False

    def validate(self) -> None:
        if self.scalar and self.axes:
            raise ValueError("Scalar previews do not use display axes")
        if len(self.axes) > 2 or len(set(self.axes)) != len(self.axes):
            raise ValueError("Choose one or two distinct display axes")
        if any(i < 0 for i in (*self.axes, *self.fixed, *self.starts)):
            raise ValueError("Array axes/indices must be nonnegative")
        if len(self.fixed) > 64 or len(self.starts) > 2 or len(self.counts) > 2:
            raise ValueError("Array slice settings exceed dimension bounds")
        if any(not 1 <= n <= 4096 for n in self.counts):
            raise ValueError(
                "Slice windows contain between 1 and 4096 positions per axis"
            )
        if self.component not in ("Magnitude", "Real", "Imaginary"):
            raise ValueError("Unknown complex display component")
