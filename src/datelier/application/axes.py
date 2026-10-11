"""Atomic axis drafts and one-shot range requests, independent of native plots."""

import math
from dataclasses import dataclass, field
from enum import IntEnum

type Range = tuple[float, float]
type Ranges = tuple[Range, Range]


class AxisScale(IntEnum):
    LINEAR = 0
    SYMMETRIC_LOG = 1
    LOG_10 = 2


def validate_range(bounds: Range, logarithmic: bool = False) -> None:
    low, high = bounds
    if not all(math.isfinite(v) for v in bounds) or low >= high:
        raise ValueError("Minimum and maximum must be finite, with minimum < maximum.")
    if logarithmic and low <= 0:
        raise ValueError("Log scale requires a positive minimum.")


@dataclass
class AxisState:
    enabled: tuple[bool, bool] = (True, True)
    limits: Ranges = ((0, 1), (0, 1))
    scales: list[int] = field(default_factory=lambda: [0, 0])
    draft: list[list[float]] = field(default_factory=lambda: [[0, 1], [0, 1]])
    draft_scales: list[int] = field(default_factory=lambda: [0, 0])
    pending: bool = False
    _scope: object = field(default=None, repr=False)

    def bind(self, scope: object, enabled: tuple[bool, bool]) -> bool:
        if scope == self._scope and enabled == self.enabled:
            return False
        self._scope, self.enabled = scope, enabled
        self.limits, self.scales, self.pending = ((0, 1), (0, 1)), [0, 0], False
        self.begin_edit()
        return True

    def begin_edit(self) -> None:
        self.draft = [list(v) for v in self.limits]
        self.draft_scales = self.scales.copy()

    def accept(self) -> None:
        ranges = [
            (v[0], v[1]) if self.enabled[i] else self.limits[i]
            for i, v in enumerate(self.draft)
        ]
        scales = [
            self.draft_scales[i] if enabled else self.scales[i]
            for i, enabled in enumerate(self.enabled)
        ]
        for i, enabled in enumerate(self.enabled):
            if enabled:
                if scales[i] not in tuple(AxisScale):
                    raise ValueError("Unknown axis scale.")
                validate_range(ranges[i], scales[i] == AxisScale.LOG_10)
        self.limits, self.scales, self.pending = (ranges[0], ranges[1]), scales, True

    def observe(self, limits: Ranges) -> None:
        self.limits = limits

    def take_request(self) -> Ranges | None:
        request = self.limits if self.pending else None
        self.pending = False
        return request
