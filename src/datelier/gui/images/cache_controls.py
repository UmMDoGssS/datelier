"""Focused image provenance and configurable retained cache budgets."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.inspection.images.prepare import default_range
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.types import ImageMetadata


def cache_controls(settings: ImageSettings, metadata: ImageMetadata) -> ImageSettings:
    if not imgui.tree_node("Image details and caches"):
        return settings
    imgui.text_wrapped(metadata.description)
    imgui.text("Wheel to zoom; drag to pan. Hover for original pixel values.")
    if metadata.orientation != 1:
        imgui.text(
            f"EXIF {metadata.orientation} · "
            f"source {metadata.source_width}×{metadata.source_height}"
        )
    lo, hi = settings.display.value_range or default_range(metadata.dtype)
    imgui.text(f"Display values {lo:g}–{hi:g}")
    for label, name, minimum in (
        ("CPU MiB", "cpu_bytes", 1),
        ("GPU MiB", "gpu_bytes", 1),
        ("Decoded disk MiB", "disk_bytes", 0),
    ):
        imgui.set_next_item_width(120)
        changed, value = imgui.input_int(
            label, getattr(settings, name) // (1024 * 1024)
        )
        if changed and value >= minimum:
            size_bytes = value * 1024 * 1024
            if name == "cpu_bytes":
                settings = replace(settings, cpu_bytes=size_bytes)
            elif name == "gpu_bytes":
                settings = replace(settings, gpu_bytes=size_bytes)
            else:
                settings = replace(settings, disk_bytes=size_bytes)
    imgui.tree_pop()
    return settings
