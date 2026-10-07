"""Explicit collection scope and pixel-sampling controls, without source reads."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.inspection.images.profile_types import (
    ImageProfileSettings,
    ImageScopeMode,
    PixelScope,
)


def profile_controls(settings: ImageProfileSettings) -> ImageProfileSettings:
    if not imgui.collapsing_header("Image collection scope"):
        return settings
    scope = settings.scope
    modes = list(ImageScopeMode)
    _, choice = imgui.combo(
        "Image records", modes.index(scope.mode), [mode.value for mode in modes]
    )
    scope = replace(scope, mode=modes[choice])
    if scope.mode == ImageScopeMode.RANGE:
        _, start = imgui.input_int("First image row", scope.start)
        scope = replace(scope, start=max(1, start))
    if scope.mode in (ImageScopeMode.RANGE, ImageScopeMode.RANDOM):
        _, count = imgui.input_int("Image record count", scope.count)
        scope = replace(scope, count=max(1, count))
    if scope.mode == ImageScopeMode.RANDOM:
        _, seed = imgui.input_int("Image sample seed", scope.seed)
        scope = replace(scope, seed=max(0, min(2**32 - 1, seed)))
    pixels = list(PixelScope)
    _, choice = imgui.combo(
        "Profile pixels", pixels.index(settings.pixels), [mode.value for mode in pixels]
    )
    settings = replace(settings, scope=scope, pixels=pixels[choice])
    if settings.pixels == PixelScope.SAMPLE:
        _, count = imgui.input_int("Pixels per image", settings.pixel_count)
        _, seed = imgui.input_int("Pixel sample seed", settings.pixel_seed)
        settings = replace(
            settings, pixel_count=max(1, count), pixel_seed=max(0, min(2**32 - 1, seed))
        )
    _, bins = imgui.input_int("Image histogram bins", settings.bins)
    return replace(settings, bins=max(1, min(256, bins)))
