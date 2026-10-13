"""GUI-thread owning textures; bounded cache and per-frame upload work."""

from collections import OrderedDict
from collections.abc import Hashable

import numpy as np
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.gui.records.media.sampling import NearestSampling
from datelier.inspection.references import AssetPreview


class TextureCache:
    def __init__(self) -> None:
        self._textures: OrderedDict[Hashable, tuple[hello_imgui.TextureGpu, int]] = (
            OrderedDict()
        )
        self._used: set[Hashable] = set()
        self._invalid = False
        self.uploads = 0
        self.shown = 0
        self.sampling = NearestSampling()

    @property
    def retained_bytes(self) -> int:
        return sum(size for _, size in self._textures.values())

    def invalidate(self) -> None:
        self._invalid = True

    def begin_frame(self) -> None:
        if self._invalid:
            self.clear()
            self._invalid = False
        self._used.clear()
        self.uploads = 0

    def clear(self) -> None:
        self._textures.clear()
        self._used.clear()

    def close(self) -> None:
        self.clear()
        self.sampling.close()

    def draw(self, preview: AssetPreview, limit: int, extent: float) -> bool:
        rgba = preview.rgba
        if rgba is None:
            return False
        return self.draw_rgba((preview.asset, rgba.shape), rgba, limit, extent)

    def draw_rgba(
        self, asset: Hashable, rgba: NDArray[np.uint8], limit: int, extent: float
    ) -> bool:
        cached = self._textures.get(asset)
        if cached is None:
            if self.uploads >= 4 or rgba.nbytes > limit:
                return False
            for key in tuple(self._textures):
                if self.retained_bytes + rgba.nbytes <= limit:
                    break
                if key not in self._used:
                    del self._textures[key]
            if self.retained_bytes + rgba.nbytes > limit:
                return False
            texture = hello_imgui.create_texture_gpu_from_rgba_data(rgba)
            self._textures[asset] = cached = (texture, rgba.nbytes)
            self.uploads += 1
        self._textures.move_to_end(asset)
        self._used.add(asset)
        texture = cached[0]
        scale = min(extent / texture.width, extent / texture.height)
        with self.sampling.draw():
            imgui.image(
                imgui.ImTextureRef(texture.texture_id()),
                (texture.width * scale, texture.height * scale),
            )
        self.shown += 1
        return True
