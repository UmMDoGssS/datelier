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
bold_font: imgui.ImFont | None = None


def load_fonts() -> None:
    global bold_font
    bold_font = None
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
    bold = next(
        (
            path
            for path in (
                Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            )
            if path.is_file()
        ),
        None,
    )
    if bold:
        bold_font = hello_imgui.load_font(
            str(bold), 13, hello_imgui.FontLoadingParams(inside_assets=False)
        )
