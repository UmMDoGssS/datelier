"""GUI-thread texture ownership and pixel-space canvas rendering."""

from imgui_bundle import hello_imgui, imgui

from datelier.inspection.images.geometry import source_pixel
from datelier.inspection.images.types import PreparedImage
from datelier.inspection.images.viewport import ImageViewport


class ImageCanvas:
    def __init__(self) -> None:
        self.texture: hello_imgui.TextureGpu | None = None
        self.prepared: PreparedImage | None = None
        self.shown = 0
        self.uploads = 0
        self.hovered: tuple[int, int] | None = None
        self.readout: tuple[object, ...] | None = None
        self.bounds: tuple[float, float, float, float] | None = None
        self.clicked: tuple[float, float] | None = None
        self._drag_view: ImageViewport | None = None

    @property
    def retained_bytes(self) -> int:
        return self.prepared.rgba.nbytes if self.texture and self.prepared else 0

    def clear(self) -> None:
        self.texture = None
        self.prepared = None
        self.bounds = None
        self.hovered = None
        self.readout = None
        self._drag_view = None
        self.clicked = None

    def show(
        self,
        prepared: PreparedImage | None,
        viewport: ImageViewport,
        size: tuple[float, float],
        limit: int,
    ) -> ImageViewport:
        origin = imgui.get_cursor_screen_pos()
        imgui.invisible_button(
            "Image canvas",
            size,
            imgui.ButtonFlags_.mouse_button_left
            | imgui.ButtonFlags_.mouse_button_middle,
        )
        hovered = imgui.is_item_hovered()
        active = imgui.is_item_active()
        self.bounds = (origin.x, origin.y, size[0], size[1])
        self.clicked = None
        if hovered and imgui.is_mouse_released(0):
            delta = imgui.get_mouse_drag_delta(0)
            if abs(delta.x) < 6 and abs(delta.y) < 6:
                mouse = imgui.get_io().mouse_pos
                self.clicked = viewport.point(mouse.x - origin.x, mouse.y - origin.y)
        draw = imgui.get_window_draw_list()
        draw.add_rect_filled(
            origin,
            (origin.x + size[0], origin.y + size[1]),
            imgui.get_color_u32((0.12, 0.12, 0.12, 1)),
        )
        if prepared is not self.prepared:
            self.texture = None
            self.prepared = prepared
            if prepared is not None and prepared.rgba.nbytes <= limit:
                self.texture = hello_imgui.create_texture_gpu_from_rgba_data(
                    prepared.rgba
                )
                self.uploads += 1
        self.hovered = self.readout = None
        if prepared is not None and self.texture is not None:
            window, metadata = prepared.window, prepared.metadata
            x = origin.x + (window.left - viewport.left) * viewport.zoom
            y = origin.y + (window.top - viewport.top) * viewport.zoom
            draw.push_clip_rect(origin, (origin.x + size[0], origin.y + size[1]), True)
            draw.add_image(
                imgui.ImTextureRef(self.texture.texture_id()),
                (x, y),
                (x + window.width * viewport.zoom, y + window.height * viewport.zoom),
            )
            draw.pop_clip_rect()
            self.shown += 1
            if hovered:
                mouse = imgui.get_io().mouse_pos
                px, py = viewport.point(mouse.x - origin.x, mouse.y - origin.y)
                ix = window.left + (int(px) - window.left) // window.step * window.step
                iy = window.top + (int(py) - window.top) // window.step * window.step
                values = prepared.pixel(ix, iy)
                if values is not None:
                    self.hovered, self.readout = (ix, iy), values
                    sx, sy = source_pixel(
                        ix,
                        iy,
                        metadata.source_width,
                        metadata.source_height,
                        metadata.orientation,
                    )
                    imgui.begin_tooltip()
                    imgui.text(f"Pixel ({ix}, {iy}) · source ({sx}, {sy})")
                    if metadata.mode == "Numeric":
                        imgui.text_unformatted(
                            f"Channel {prepared.display.channel}: {values}"
                        )
                        mapping, catalog = (
                            prepared.locator.mapping,
                            prepared.locator.catalog,
                        )
                        if mapping is not None and catalog is not None:
                            shape = catalog.member(mapping.member).shape
                            indices = list(
                                prepared.display.fixed
                                or mapping.fixed
                                or (0,) * len(shape)
                            )
                            indices[mapping.record_axis] = (
                                prepared.locator.source_index or 0
                            )
                            indices[mapping.display_axes[0]] = iy
                            indices[mapping.display_axes[1]] = ix
                            if mapping.channel_axis is not None:
                                indices[mapping.channel_axis] = (
                                    prepared.display.channel or 0
                                )
                            imgui.text(f"Source index {tuple(indices)}")
                    else:
                        imgui.text_unformatted(
                            f"{', '.join(metadata.channels)}: {values}"
                        )
                    if window.step > 1:
                        imgui.text(
                            f"Overview: every {window.step} pixels. "
                            "Zoom for exact pixels."
                        )
                    imgui.end_tooltip()
        if hovered:
            io = imgui.get_io()
            if io.mouse_wheel:
                viewport = viewport.zoom_at(
                    viewport.zoom * 1.25**io.mouse_wheel,
                    io.mouse_pos.x - origin.x,
                    io.mouse_pos.y - origin.y,
                )
        if active:
            if self._drag_view is None:
                self._drag_view = viewport
            button = 0 if imgui.get_io().mouse_down[0] else 2
            delta = imgui.get_mouse_drag_delta(button)
            viewport = self._drag_view.pan(delta.x, delta.y)
        else:
            self._drag_view = None
        return viewport
