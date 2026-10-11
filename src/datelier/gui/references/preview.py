"""A reusable prepared reference preview and explicit ambiguity chooser."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.media.records import ReferenceController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.inputs import TextField
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import label_text, target
from datelier.gui.references.cache import PreviewTextures
from datelier.inspection.references import AssetPreview, Resolution


class CandidateList(Component):
    def __init__(
        self, read: Callable[[], Resolution | None], choose: Callable[[str], None]
    ) -> None:
        super().__init__("candidates")
        self.read, self.choose = read, choose

    def render(self, frame: FrameContext) -> None:
        resolution = self.read()
        if resolution is None:
            return
        imgui.text_wrapped(resolution.message)
        if resolution.candidates and imgui.begin_child("candidates", (0, 130)):
            clipper = imgui.ListClipper()
            clipper.begin(len(resolution.candidates))
            while clipper.step():
                for i in range(clipper.display_start, clipper.display_end):
                    path = resolution.candidates[i]
                    if imgui.selectable(label_text(str(path)) + f"##{i}", False)[0]:
                        self.choose(str(path))
                    target(frame.child(str(i)), "choose")
        if resolution.candidates:
            imgui.end_child()


class ReferenceMappingPopup(Container):
    def __init__(self, model: ReferenceController) -> None:
        self.model = model
        self._target = None
        self.apply = CommandButton("apply", "Use file", lambda: self.use(model.path))
        super().__init__(
            "mapping-popup",
            (
                CandidateList(
                    lambda: model.target.resolution if model.target else None,
                    self.choose,
                ),
                TextField(
                    "path",
                    "Exact file path",
                    lambda: model.path,
                    lambda v: setattr(model, "path", v),
                ),
                self.apply,
            ),
        )

    def use(self, path: str) -> None:
        self.model.map_target(path)
        imgui.close_current_popup()

    def choose(self, path: str) -> None:
        try:
            self.use(path)
            self.apply.error = ""
        except ValueError as error:
            self.apply.error = str(error)

    def render(self, frame: FrameContext) -> None:
        if self._target is not self.model.target:
            self._target = self.model.target
            self.apply.error = ""
        super().render(frame)


class ReferencePreview(Container, ABC):
    def __init__(
        self,
        model: ReferenceController,
        textures: PreviewTextures,
        popup: ReferenceMappingPopup,
        column: str,
        value: str,
        label: str,
        extent: float,
    ) -> None:
        super().__init__("reference", (popup,))
        self.model, self.textures = model, textures
        self.column, self.value, self.label, self.extent = column, value, label, extent

    def render(self, frame: FrameContext) -> None:
        resolution, preview = self.model.jobs.get(self.column, self.value)
        shown = self.render_inline(preview, frame)
        frame.measure("shown", (float(shown), 1.0))
        target(frame, "preview")
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text_unformatted(self.value[:4096])
            if resolution:
                imgui.text_wrapped(resolution.message)
                if resolution.asset:
                    imgui.text_unformatted(str(resolution.asset.path))
            if preview:
                imgui.text_wrapped(preview.description or preview.message)
                if preview.text:
                    imgui.text_unformatted(preview.text)
                if not shown:
                    self.textures.draw(preview, self.model.jobs.settings.gpu_bytes, 128)
            elif resolution and resolution.asset:
                imgui.text("Preparing preview…")
            imgui.end_tooltip()
        if resolution and (resolution.message or resolution.candidates):
            if imgui.small_button("Choose reference"):
                self.model.choose_target(self.column, self.value, resolution)
                imgui.open_popup("Reference mapping")
            target(frame, "choose")
        imgui.set_next_window_size((400, 0), imgui.Cond_.appearing)
        if imgui.begin_popup("Reference mapping"):
            super().render(frame)
            imgui.end_popup()

    def image(self, preview: AssetPreview | None) -> bool:
        return bool(
            preview
            and self.model.thumbnails
            and self.textures.draw(
                preview, self.model.jobs.settings.gpu_bytes, self.extent
            )
        )

    @abstractmethod
    def render_inline(
        self, preview: AssetPreview | None, frame: FrameContext
    ) -> bool: ...


class TableReferencePreview(ReferencePreview):
    def render_inline(self, preview: AssetPreview | None, frame: FrameContext) -> bool:
        shown = self.image(preview)
        if not shown:
            imgui.text_unformatted(self.label)
        return shown


class GalleryReferencePreview(ReferencePreview):
    def render_inline(self, preview: AssetPreview | None, frame: FrameContext) -> bool:
        shown = self.image(preview)
        if not shown:
            imgui.text_wrapped(
                (preview.description or preview.message) if preview else self.label
            )
        if preview and preview.text:
            imgui.text_wrapped(preview.text[:256])
            frame.measure("excerpt", (float(min(256, len(preview.text))), 256.0))
        return shown
