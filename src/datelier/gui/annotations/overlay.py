"""Render cached worker scenes and send explicit scoped box-picking commands."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.annotations.controller import AnnotationController
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.records.pixels import PixelSurface
from datelier.inspection.annotations.association_types import AssociatedBox
from datelier.inspection.annotations.overlay import hits
from datelier.inspection.images.viewport import ImageViewport

COLORS = (
    (1.0, 0.55, 0.1, 1.0),
    (0.2, 0.9, 0.4, 1.0),
    (0.5, 0.7, 1.0, 1.0),
    (0.95, 0.35, 0.8, 1.0),
    (0.9, 0.9, 0.15, 1.0),
    (0.3, 0.95, 0.95, 1.0),
)


class SelectedBox(Component):
    def __init__(self, model: AnnotationController) -> None:
        super().__init__("selected-box")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        box = self.model.selected
        if box:
            record = box.box.record
            imgui.text_wrapped(
                f"Selected {record.class_name} · source row {box.origin.row_id} · "
                f"{record.asset.path}: {record.location} · original {record.original} "
                f"({record.coordinates}) · pixel {box.box.xyxy}"
            )
            if box.box.diagnostics:
                imgui.text_wrapped("; ".join(box.box.diagnostics))


class AnnotationOverlay(Container):
    def __init__(
        self,
        model: AnnotationController,
        surface: PixelSurface,
        viewport: Callable[[], ImageViewport],
        select: Callable[[AssociatedBox], None],
    ) -> None:
        super().__init__("overlay", (SelectedBox(model),))
        self.model, self.surface, self.viewport, self.select = (
            model,
            surface,
            viewport,
            select,
        )
        self.drawn = self.labels_shown = 0

    def render(self, frame: FrameContext) -> None:
        model, surface = self.model, self.surface
        prepared, bounds = surface.prepared, surface.bounds
        self.drawn = self.labels_shown = 0
        if prepared is None or bounds is None:
            model.scene.abandon()
            return
        if model.selected and (
            model.selected.origin != prepared.locator.origin
            or not model.read_view().overlay.includes(model.selected)
        ):
            model.selected = None
        model.scene.request(
            prepared.locator.origin,
            bounds,
            self.viewport(),
            model.read_view().overlay,
            model.selected,
            imgui.get_text_line_height(),
        )
        scene = model.scene.active
        if model.jobs.active is None:
            return
        if scene is None:
            imgui.text(
                model.scene.message
                or (
                    "Preparing viewport boxes…"
                    if model.read_view().overlay.enabled
                    else "Box overlay hidden"
                )
            )
            super().render(frame)
            return
        colors = {
            source.name: imgui.get_color_u32(COLORS[index % len(COLORS)])
            for index, source in enumerate(model.source_choices)
        }
        selected_color = imgui.get_color_u32((1.0, 1.0, 1.0, 1.0))
        draw = imgui.get_window_draw_list()
        x, y, width, height = bounds
        draw.push_clip_rect((x, y), (x + width, y + height), True)
        for item in scene.strokes:
            x1, y1, x2, y2 = item.clipped
            draw.add_rect(
                (x1, y1),
                (x2, y2),
                selected_color if item.selected else colors[item.box.source_id],
                thickness=3 if item.selected else 1.5,
            )
        for label in scene.labels:
            draw.add_text(
                label.position,
                selected_color if label.selected else colors[label.source_id],
                label.text,
            )
        draw.pop_clip_rect()
        self.drawn, self.labels_shown = len(scene.boxes), len(scene.labels)
        frame.measure("drawn", (float(self.drawn), float(self.labels_shown)))
        if surface.clicked is not None:
            choices = tuple(
                item.box for item in scene.boxes if hits(item.box, surface.clicked)
            )
            if choices:
                index = (
                    (choices.index(model.selected) + 1) % len(choices)
                    if imgui.get_io().key_ctrl and model.selected in choices
                    else 0
                )
                self.select(choices[index])
        imgui.text(
            f"{self.drawn:,}/{scene.visible_count:,} visible boxes · "
            f"{self.labels_shown:,}/{scene.label_candidates:,} labels"
        )
        super().render(frame)

    def close(self) -> None:
        self.model.scene.abandon()
