"""Canvas-aligned prepared box rendering and scoped linked picking."""

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.annotations.outcomes import open_image
from datelier.inspection.annotations.association_types import (
    AssociatedBox,
    PreparedAnnotations,
)
from datelier.inspection.annotations.overlay import (
    OverlaySettings,
    hits,
    screen_box,
    visible,
)
from datelier.inspection.images.viewport import ImageViewport

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession
    from datelier.gui.images.canvas import ImageCanvas

COLORS = (
    (1.0, 0.55, 0.1, 1.0),
    (0.2, 0.9, 0.4, 1.0),
    (0.5, 0.7, 1.0, 1.0),
    (0.95, 0.35, 0.8, 1.0),
    (0.9, 0.9, 0.15, 1.0),
    (0.3, 0.95, 0.95, 1.0),
)


class AnnotationOverlay:
    def __init__(self) -> None:
        self.selected: AssociatedBox | None = None
        self.drawn: list[tuple[AssociatedBox, tuple[float, float, float, float]]] = []
        self.visible_count = 0
        self._bound: PreparedAnnotations | None = None
        self._colors: dict[str, tuple[float, float, float, float]] = {}

    def bind(self, prepared: PreparedAnnotations | None) -> None:
        if prepared is not self._bound:
            self.selected = None
            self.drawn.clear()
            self._bound = prepared
            self._colors = (
                {
                    source.recipe.id: COLORS[index % len(COLORS)]
                    for index, source in enumerate(prepared.sources)
                }
                if prepared
                else {}
            )

    def select(self, box: AssociatedBox, owner: FileSession) -> None:
        prepared = self._bound
        active = owner.loader.active
        if (
            prepared is not None
            and active is not None
            and (prepared.file_id, prepared.view_name, prepared.revision)
            == (owner.identity, owner.view_name, active.dataset.revision)
            and box in prepared.by_image.get(box.origin, ())
        ):
            open_image(owner, prepared, box.origin.row_id)
            self.selected = box

    def show(
        self,
        canvas: ImageCanvas,
        viewport: ImageViewport,
        settings: OverlaySettings,
        owner: FileSession,
    ) -> None:
        self.drawn.clear()
        self.visible_count = 0
        prepared = self._bound
        image = canvas.prepared
        bounds = canvas.bounds
        if prepared is None or image is None or bounds is None:
            return
        boxes = prepared.by_image.get(image.locator.origin, ())
        if self.selected is not None and (
            self.selected.origin != image.locator.origin
            or not settings.includes(self.selected)
        ):
            self.selected = None
        x, y, width, height = bounds
        draw = imgui.get_window_draw_list()
        draw.push_clip_rect((x, y), (x + width, y + height), True)
        choices: list[AssociatedBox] = []
        for box in boxes:
            if not settings.includes(box) or not visible(
                box, viewport, (width, height)
            ):
                continue
            self.visible_count += 1
            if len(self.drawn) >= settings.limit:
                continue
            edges = screen_box(box, viewport, (x, y))
            x1, y1, x2, y2 = (
                max(x, min(x + width, edges[0])),
                max(y, min(y + height, edges[1])),
                max(x, min(x + width, edges[2])),
                max(y, min(y + height, edges[3])),
            )
            color = (
                (1.0, 1.0, 1.0, 1.0)
                if self.selected == box
                else self._colors[box.source_id]
            )
            draw.add_rect(
                (x1, y1),
                (x2, y2),
                imgui.get_color_u32(color),
                thickness=3 if self.selected == box else 1.5,
            )
            record = box.box.record
            if settings.labels or (settings.scores and record.score is not None):
                label = record.class_name[:60] if settings.labels else ""
                if settings.scores and record.score is not None:
                    label += f" {record.score:.3g}"
                draw.add_text(
                    (x1 + 3, max(y, y1 - imgui.get_text_line_height())),
                    imgui.get_color_u32(color),
                    label,
                )
            self.drawn.append((box, edges))
            if canvas.clicked is not None and hits(box, canvas.clicked):
                choices.append(box)
        draw.pop_clip_rect()
        if choices:
            choice = 0
            if imgui.get_io().key_ctrl and self.selected in choices:
                choice = (choices.index(self.selected) + 1) % len(choices)
            self.select(choices[choice], owner)
        if self.visible_count > len(self.drawn):
            imgui.text(
                f"Showing {len(self.drawn):,}/{self.visible_count:,} visible boxes. "
                "Raise Visible box limit to show more."
            )
        if self.selected is not None:
            box = self.selected
            raw = box.box.record
            imgui.text_wrapped(
                f"Selected {raw.class_name} · source row {box.origin.row_id} · "
                f"{raw.asset.path.name}: {raw.location} · "
                f"original {raw.original} ({raw.coordinates}) · pixel {box.box.xyxy}"
            )
            if box.box.diagnostics:
                imgui.text_wrapped("; ".join(box.box.diagnostics))
