"""Framebuffer gate for sharp previews/canvases and restored UI sampling."""

import argparse
import json
from pathlib import Path
from uuid import UUID

import numpy as np
from imgui_bundle import hello_imgui, imgui, immapp
from PIL import Image

from datelier.core import DatasetRevision
from datelier.gui.records.media import PixelSurface, TextureCache
from datelier.inspection.images.types import (
    ImageDisplay,
    ImageLocator,
    ImageMetadata,
    ImageOrigin,
    ImageWindow,
    PreparedImage,
)
from datelier.inspection.images.viewport import ImageViewport


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fractional", action="store_true")
    args = parser.parse_args()
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    rgba[:, :, 3] = 255
    rgba[::2, ::2, :3] = 255
    rgba[1::2, 1::2, :3] = 255
    rgba.flags.writeable = False
    prepared = PreparedImage(
        ImageLocator(
            ImageOrigin(
                "fixture", "", DatasetRevision(UUID(int=1), UUID(int=2)), 0, "pixels"
            )
        ),
        ImageMetadata(4, 4, 4, 4, ("R", "G", "B", "A"), rgba.dtype, "RGBA"),
        ImageWindow(width=4, height=4),
        ImageDisplay(),
        rgba,
        rgba,
        0,
    )
    previews, surface = TextureCache(), PixelSurface()
    control: hello_imgui.TextureGpu | None = None
    rectangles: list[tuple[float, float, float, float]] = []
    frames = 0
    zoom = 19.75 if args.fractional else 32.0
    viewport = ImageViewport(zoom, 0.15 if args.fractional else 0, 0)

    def rect() -> None:
        start, end = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        rectangles.append((start.x, start.y, end.x - start.x, end.y - start.y))

    def draw() -> None:
        nonlocal frames, control
        rectangles.clear()
        if control is None:
            control = hello_imgui.create_texture_gpu_from_rgba_data(rgba)
        previews.begin_frame()
        assert previews.draw_rgba("checkerboard", rgba, 1024, 4 * zoom)
        rect()
        imgui.same_line()
        surface.draw(prepared, viewport, (3 * zoom, 3 * zoom), 1024)
        rect()
        imgui.same_line()
        imgui.image(imgui.ImTextureRef(control.texture_id()), (4 * zoom, 4 * zoom))
        rect()
        assert surface.prepared and surface.prepared.pixel(0, 0) == (255, 255, 255, 255)
        assert previews.retained_bytes == surface.retained_bytes == 64
        frames += 1
        if frames >= 15:
            hello_imgui.get_runner_params().app_shall_exit = True

    def close() -> None:
        nonlocal control
        previews.close()
        surface.close()
        control = None

    params = hello_imgui.RunnerParams()
    params.app_window_params.window_geometry.size = (600, 240)
    params.app_window_params.window_title = "Datelier pixel sampling acceptance"
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    )
    params.ini_disable = True
    params.callbacks.show_gui, params.callbacks.before_exit = draw, close
    immapp.run(params)
    screenshot = hello_imgui.final_app_window_screenshot()
    colors = []
    for x, y, width, height in rectangles:
        region = screenshot[
            int(y) + 3 : int(y + height) - 3,
            int(x) + 3 : int(x + width) - 3,
            :3,
        ]
        colors.append(np.unique(region.reshape(-1, 3), axis=0))
    original = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
    np.testing.assert_array_equal(colors[0], original)
    np.testing.assert_array_equal(colors[1], original)
    assert len(colors[2]) > 2  # Following draws retain the normal linear sampler.
    assert previews.retained_bytes == surface.retained_bytes == 0
    output = Path(
        "/tmp/datelier-image-sampling" + ("-fractional" if args.fractional else "")
    )
    Image.fromarray(screenshot).save(output.with_suffix(".png"))
    report = {
        "frames": frames,
        "fractional_zoom_pan": args.fractional,
        "preview_original_colors": len(colors[0]),
        "canvas_original_colors": len(colors[1]),
        "following_linear_colors": len(colors[2]),
        "resources_released": True,
    }
    output.with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
