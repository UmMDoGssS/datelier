"""Small stateless native boundary helpers."""

from imgui_bundle import imgui

from datelier.gui.components.layout import FrameContext


def label_text(value: str) -> str:
    """Keep source hashes visible without letting ImGui interpret ID markers."""
    return value.replace("#", "#\u200b")


def target(frame: FrameContext, key: str) -> None:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    frame.record(key, ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2))


def window_close_target(frame: FrameContext) -> None:
    position, size = imgui.get_window_pos(), imgui.get_window_size()
    frame.record(
        "close-window",
        (position.x + size.x - 13, position.y + imgui.get_frame_height() / 2),
    )


def help_tip(text: str) -> None:
    imgui.text_disabled("(?)")
    if imgui.is_item_hovered():
        imgui.set_tooltip(text)


def number(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
