"""Shared image/array pixel geometry and native texture ownership.

Display buffers are separate from original values. Use sharp nearest-neighbor
pixels for inspection; image content is never tinted by table shading. Color
ramps/ranges affect display only, including explicit nonfinite colors. Owners
release textures before renderer shutdown; record views consume these primitives
without making a second authoritative payload cache.
"""

from datelier.gui.records.media.pixels import PixelSurface as PixelSurface
from datelier.gui.records.media.textures import TextureCache as TextureCache
