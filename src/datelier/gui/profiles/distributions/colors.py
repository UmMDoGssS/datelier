"""Stable series colors shared by profile plots, legends, and statistics."""

from colorsys import hsv_to_rgb
from hashlib import blake2b

from imgui_bundle import imgui


def profile_color(name: str, peers: tuple[str, ...] = ()) -> imgui.ImVec4:
    """Maximize minimum circular hue distance for this displayed series set.

    Sorted identities make assignments independent of drawing order. A stable
    rotation retains deterministic colors across modes and restored sessions.
    Changing the set can reassign colors; manual comparison colors stay explicit.
    """
    names = tuple(sorted(set(peers)))
    hue = int.from_bytes(blake2b(name.encode(), digest_size=4).digest()) / 2**32
    if len(names) > 1 and name in names:
        rotation = (
            int.from_bytes(blake2b("\0".join(names).encode(), digest_size=4).digest())
            / 2**32
        )
        hue = (rotation + names.index(name) / len(names)) % 1
    return imgui.ImVec4(*hsv_to_rgb(hue, 0.78, 0.95), 1)
