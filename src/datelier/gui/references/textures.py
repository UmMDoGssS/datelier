"""GUI-thread owning textures; bounded cache and per-frame upload work."""

from collections import OrderedDict

from imgui_bundle import hello_imgui, imgui

from datelier.inspection.references.types import AssetIdentity, AssetPreview


class PreviewTextures:
    def __init__(self) -> None:
        self._textures: OrderedDict[
            AssetIdentity, tuple[hello_imgui.TextureGpu, int]
        ] = OrderedDict()
        self._used: set[AssetIdentity] = set()
        self._invalid = False
        self.uploads = 0
        self.shown = 0

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

    def show(self, preview: AssetPreview, limit: int, extent: float) -> bool:
        rgba = preview.rgba
        if rgba is None:
            return False
        asset = preview.asset
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
        imgui.image(
            imgui.ImTextureRef(texture.texture_id()),
            (texture.width * scale, texture.height * scale),
        )
        self.shown += 1
        return True
