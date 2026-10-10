"""Worker-prepared viewport geometry and conservative non-overlapping labels."""

from dataclasses import dataclass
from threading import Event

from datelier.inspection.annotations.associate import check_cancelled
from datelier.inspection.annotations.association_types import AssociatedBox
from datelier.inspection.annotations.label_layout import LabelLayout
from datelier.inspection.annotations.overlay import OverlaySettings, screen_box, visible
from datelier.inspection.images.viewport import ImageViewport

type Edges = tuple[float, float, float, float]


@dataclass(frozen=True)
class BoxDrawing:
    box: AssociatedBox
    clipped: Edges
    selected: bool


@dataclass(frozen=True)
class BoxLabel:
    source_id: str
    position: tuple[float, float]
    text: str
    selected: bool


@dataclass(frozen=True)
class OverlayScene:
    boxes: tuple[BoxDrawing, ...]
    strokes: tuple[BoxDrawing, ...]
    labels: tuple[BoxLabel, ...]
    visible_count: int
    label_candidates: int


def prepare_scene(
    boxes: tuple[AssociatedBox, ...],
    bounds: Edges,
    viewport: ImageViewport,
    settings: OverlaySettings,
    selected: AssociatedBox | None,
    line_height: float,
    stop: Event,
) -> OverlayScene:
    x, y, width, height = bounds
    drawings: list[BoxDrawing] = []
    labels: list[BoxLabel] = []
    visible_count = 0
    for index, box in enumerate(boxes):
        if index % 512 == 0:
            check_cancelled(stop)
        if not settings.includes(box) or not visible(box, viewport, (width, height)):
            continue
        visible_count += 1
        if len(drawings) >= settings.limit:
            continue
        edges = screen_box(box, viewport, (x, y))
        clipped = (
            max(x, min(x + width, edges[0])),
            max(y, min(y + height, edges[1])),
            max(x, min(x + width, edges[2])),
            max(y, min(y + height, edges[3])),
        )
        chosen = selected == box
        drawings.append(BoxDrawing(box, clipped, chosen))
        record = box.box.record
        if settings.labels or settings.scores and record.score is not None:
            text = record.class_name[:60] if settings.labels else ""
            if settings.scores and record.score is not None:
                text += f" {record.score:.3g}"
            labels.append(
                BoxLabel(
                    box.source_id,
                    (clipped[0] + 3, max(y, clipped[1] - line_height)),
                    text,
                    chosen,
                )
            )
    layout = LabelLayout()
    drawn_labels: list[BoxLabel] = []
    for label in sorted(labels, key=lambda item: not item.selected):
        # Reserve up to one em per source code point. This deliberately leaves
        # more space than the common proportional-font advances, and needs no
        # GUI/font access in a worker. Native text remains clipped to the canvas.
        px, py = label.position
        rect = (
            px,
            py,
            min(x + width, px + line_height * len(label.text)),
            min(y + height, py + line_height),
        )
        if settings.overlapping_labels or layout.reserve(rect):
            drawn_labels.append(label)
    check_cancelled(stop)
    # Identical strokes need one native draw while every original box remains
    # available for picking, cycling, profiles and provenance. Draw the selected
    # stroke last so repeated neighbors cannot cover its highlight.
    strokes = {
        (item.clipped, item.box.source_id, item.selected): item for item in drawings
    }
    return OverlayScene(
        tuple(drawings),
        tuple(sorted(strokes.values(), key=lambda item: item.selected)),
        tuple(drawn_labels),
        visible_count,
        len(labels),
    )
