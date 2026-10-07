"""Load installed Linux Unicode fonts once during native GUI initialization."""

from pathlib import Path

from imgui_bundle import hello_imgui, imgui

BASE_FONTS = (
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)
FALLBACK_FONTS = (
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path(__file__).parent / "assets" / "fonts" / "NotoEmoji.ttf",
)


def load_fonts() -> None:
    base = next((path for path in BASE_FONTS if path.is_file()), None)
    if base is not None:
        settings = hello_imgui.FontLoadingParams(inside_assets=False)
        hello_imgui.load_font(str(base), 13, settings)
    else:
        imgui.get_io().fonts.add_font_default()
    for path in FALLBACK_FONTS:
        if path.is_file():
            settings = hello_imgui.FontLoadingParams(
                inside_assets=False, merge_to_last_font=True
            )
            hello_imgui.load_font(str(path), 13, settings)
