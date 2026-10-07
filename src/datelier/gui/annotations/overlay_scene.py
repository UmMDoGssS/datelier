"""Cached viewport geometry and label layout from immutable prepared boxes."""

from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.inspection.annotations.association_types import AssociatedBox
from datelier.inspection.annotations.label_layout import LabelLayout
from datelier.inspection.annotations.overlay import OverlaySettings, screen_box, visible
from datelier.inspection.images.viewport import ImageViewport

type Edges = tuple[float, float, float, float]
type Label = tuple[tuple[float, float], int, str]


@dataclass(frozen=True)
class BoxDrawing:
    box: AssociatedBox
    edges: Edges
    clipped: Edges
    color: int
    selected: bool


@dataclass(frozen=True)
class OverlayScene:
    boxes: tuple[BoxDrawing, ...]
    labels: tuple[Label, ...]
    visible_count: int
    label_candidates: int


def prepare_scene(
    boxes: tuple[AssociatedBox, ...],
    bounds: Edges,
    viewport: ImageViewport,
    settings: OverlaySettings,
    selected: AssociatedBox | None,
    source_colors: dict[str, tuple[float, float, float, float]],
) -> OverlayScene:
    x, y, width, height = bounds
    colors = {
        source: imgui.get_color_u32(color) for source, color in source_colors.items()
    }
    selected_color = imgui.get_color_u32((1.0, 1.0, 1.0, 1.0))
    line_height = imgui.get_text_line_height()
    drawings: list[BoxDrawing] = []
    labels: list[tuple[bool, Label]] = []
    visible_count = 0
    for box in boxes:
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
        color = selected_color if chosen else colors[box.source_id]
        drawings.append(BoxDrawing(box, edges, clipped, color, chosen))
        record = box.box.record
        if settings.labels or (settings.scores and record.score is not None):
            text = record.class_name[:60] if settings.labels else ""
            if settings.scores and record.score is not None:
                text += f" {record.score:.3g}"
            labels.append(
                (
                    chosen,
                    ((clipped[0] + 3, max(y, clipped[1] - line_height)), color, text),
                )
            )
    layout = LabelLayout()
    drawn_labels: list[Label] = []
    # Reserve the selected label first so dense neighbors cannot conceal it.
    for _, label in sorted(labels, key=lambda item: not item[0]):
        position, _, text = label
        extent = imgui.calc_text_size(text)
        rect = (
            position[0],
            position[1],
            min(x + width, position[0] + extent.x),
            min(y + height, position[1] + extent.y),
        )
        if settings.overlapping_labels or layout.reserve(rect):
            drawn_labels.append(label)
    return OverlayScene(
        tuple(drawings), tuple(drawn_labels), visible_count, len(labels)
    )
