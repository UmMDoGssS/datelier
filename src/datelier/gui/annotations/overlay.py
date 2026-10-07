"""Canvas-aligned prepared box rendering and scoped linked picking."""

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.annotations.outcomes import open_image
from datelier.gui.annotations.overlay_scene import OverlayScene, prepare_scene
from datelier.inspection.annotations.association_types import (
    AssociatedBox,
    PreparedAnnotations,
)
from datelier.inspection.annotations.overlay import OverlaySettings, hits
from datelier.inspection.images.types import ImageOrigin
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
type SceneKey = tuple[
    int,
    ImageOrigin,
    tuple[float, float, float, float],
    ImageViewport,
    OverlaySettings,
    AssociatedBox | None,
    int,
    float,
    float,
]


class AnnotationOverlay:
    def __init__(self) -> None:
        self.selected: AssociatedBox | None = None
        self.drawn: list[tuple[AssociatedBox, tuple[float, float, float, float]]] = []
        self.visible_count = 0
        self.labels_shown = self.label_candidates = 0
        self._bound: PreparedAnnotations | None = None
        self._colors: dict[str, tuple[float, float, float, float]] = {}
        self._scene: OverlayScene | None = None
        self._scene_key: SceneKey | None = None
        self.scenes_prepared = 0

    def bind(self, prepared: PreparedAnnotations | None) -> None:
        if prepared is not self._bound:
            self.selected = None
            self.drawn.clear()
            self._scene = self._scene_key = None
            self.visible_count = self.labels_shown = self.label_candidates = 0
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
        prepared = self._bound
        image = canvas.prepared
        bounds = canvas.bounds
        if prepared is None or image is None or bounds is None:
            self.drawn.clear()
            self._scene = self._scene_key = None
            self.visible_count = self.labels_shown = self.label_candidates = 0
            return
        boxes = prepared.by_image.get(image.locator.origin, ())
        if self.selected is not None and (
            self.selected.origin != image.locator.origin
            or not settings.includes(self.selected)
        ):
            self.selected = None
        key = (
            id(prepared),
            image.locator.origin,
            bounds,
            viewport,
            settings,
            self.selected,
            imgui.get_font().font_id,
            imgui.get_text_line_height(),
            imgui.get_style().alpha,
        )
        if key != self._scene_key:
            self._scene = prepare_scene(
                boxes, bounds, viewport, settings, self.selected, self._colors
            )
            self._scene_key = key
            self.scenes_prepared += 1
            self.drawn = [(item.box, item.edges) for item in self._scene.boxes]
            self.visible_count = self._scene.visible_count
            self.labels_shown = len(self._scene.labels)
            self.label_candidates = self._scene.label_candidates
        scene = self._scene
        assert scene is not None
        x, y, width, height = bounds
        draw = imgui.get_window_draw_list()
        draw.push_clip_rect((x, y), (x + width, y + height), True)
        for item in scene.boxes:
            x1, y1, x2, y2 = item.clipped
            draw.add_rect(
                (x1, y1),
                (x2, y2),
                item.color,
                thickness=3 if item.selected else 1.5,
            )
        for position, color, label in scene.labels:
            draw.add_text(position, color, label)
        draw.pop_clip_rect()
        choices = (
            [box for box, _ in self.drawn if hits(box, canvas.clicked)]
            if canvas.clicked is not None
            else []
        )
        if choices:
            choice = 0
            if (
                imgui.get_io().key_ctrl
                and self.selected is not None
                and self.selected in choices
            ):
                choice = (choices.index(self.selected) + 1) % len(choices)
            self.select(choices[choice], owner)
        if self.visible_count > len(self.drawn):
            imgui.text(
                f"Showing {len(self.drawn):,}/{self.visible_count:,} visible boxes. "
                "Raise Visible box limit to show more."
            )
        if self.labels_shown < self.label_candidates:
            imgui.text(
                f"Showing {self.labels_shown:,}/{self.label_candidates:,} box labels "
                "to avoid overlap. Zoom or enable Show overlapping box labels."
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
