"""Saved overlay choices and pure viewport/picking geometry."""

from dataclasses import dataclass
from math import isfinite

from datelier.inspection.annotations.association import AssociatedBox
from datelier.inspection.images.viewport import ImageViewport


@dataclass(frozen=True)
class OverlayClass:
    source_id: str
    class_id: int | str


@dataclass(frozen=True)
class OverlaySettings:
    enabled: bool = True
    sources: tuple[str, ...] | None = None
    classes: tuple[OverlayClass, ...] | None = None
    minimum_score: float | None = None
    include_unscored: bool = True
    labels: bool = True
    scores: bool = True
    limit: int = 2000
    overlapping_labels: bool = False

    def validate(self) -> None:
        if self.minimum_score is not None and not isfinite(self.minimum_score):
            raise ValueError("Overlay score threshold must be finite")
        if self.limit < 1:
            raise ValueError("Choose a positive visible overlay limit")

    def includes(self, box: AssociatedBox) -> bool:
        raw = box.box.record
        return (
            self.enabled
            and (self.sources is None or box.source_id in self.sources)
            and (
                self.classes is None
                or OverlayClass(box.source_id, raw.class_id) in self.classes
            )
            and (
                self.include_unscored
                if raw.score is None
                else self.minimum_score is None or raw.score >= self.minimum_score
            )
        )


def screen_box(
    box: AssociatedBox, viewport: ImageViewport, origin: tuple[float, float]
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box.oriented
    return (
        origin[0] + (x1 - viewport.left) * viewport.zoom,
        origin[1] + (y1 - viewport.top) * viewport.zoom,
        origin[0] + (x2 - viewport.left) * viewport.zoom,
        origin[1] + (y2 - viewport.top) * viewport.zoom,
    )


def visible(
    box: AssociatedBox, viewport: ImageViewport, size: tuple[float, float]
) -> bool:
    x1, y1, x2, y2 = box.oriented
    return (
        x2 >= viewport.left
        and y2 >= viewport.top
        and x1 <= viewport.left + size[0] / viewport.zoom
        and y1 <= viewport.top + size[1] / viewport.zoom
    )


def hits(box: AssociatedBox, point: tuple[float, float]) -> bool:
    x1, y1, x2, y2 = box.oriented
    return x1 <= point[0] <= x2 and y1 <= point[1] <= y2
