"""Bounded native dock-layout validation shared by preferences and sessions."""

MAX_LAYOUT_BYTES = 256 * 1024


def valid_layout(layout: str) -> bool:
    try:
        size = len(layout.encode("utf8"))
    except UnicodeError:
        return False
    return not layout or (
        size <= MAX_LAYOUT_BYTES
        and "\x00" not in layout
        and "[Docking][Data]" in layout
        and "DockSpace" in layout
        and "[Window][Table preview]" in layout
    )
