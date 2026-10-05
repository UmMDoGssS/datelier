"""Stable series colors shared by profile plots, legends, and statistics."""

from colorsys import hsv_to_rgb
from hashlib import blake2b

from imgui_bundle import imgui


def profile_color(name: str) -> imgui.ImVec4:
    hue = int.from_bytes(blake2b(name.encode(), digest_size=4).digest()) / 2**32
    return imgui.ImVec4(*hsv_to_rgb(hue, 0.6, 0.95), 1)
