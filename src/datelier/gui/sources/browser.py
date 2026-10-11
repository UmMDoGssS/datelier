"""Related source browsers share prepared listings and direct-child rendering."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.sources.numeric import NumericSourceController
from datelier.application.sources.objects import ObjectController, ObjectEntry
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import label_text, target
from datelier.inspection.objects.types import NodePath


class SourceBrowser(Container, ABC):
    @property
    @abstractmethod
    def available(self) -> bool: ...


class ObjectEntryView(Component):
    def __init__(self, entry: ObjectEntry, choose: Callable[[NodePath], None]) -> None:
        super().__init__(repr(entry.path))
        self.entry, self.choose = entry, choose

    def render(self, frame: FrameContext) -> None:
        entry = self.entry
        if imgui.selectable(label_text(entry.label) + "###" + self.key, False)[0]:
            self.choose(entry.path)
        target(frame, "open")
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"{entry.kind}: {entry.preview}")
        imgui.same_line()
        imgui.text_disabled(entry.kind)


class ObjectListing(Container):
    def __init__(self, model: ObjectController) -> None:
        super().__init__("entries", ())
        self.model = model

    def render(self, frame: FrameContext) -> None:
        if imgui.begin_child("entries", (-1, 240), imgui.ChildFlags_.borders):
            clipper = imgui.ListClipper()
            clipper.begin(len(self.model.entries))
            while clipper.step():
                self.children = tuple(
                    ObjectEntryView(e, self.model.choose)
                    for e in self.model.entries[
                        clipper.display_start : clipper.display_end
                    ]
                )
                super().render(frame)
        imgui.end_child()


class ObjectDetail(Component):
    def __init__(self, model: ObjectController) -> None:
        super().__init__("detail")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        model = self.model
        if model.selected:
            imgui.text_wrapped(model.selected.label)
            imgui.text_wrapped(model.selected.kind + ": " + model.selected.preview)
        if not model.length:
            return
        imgui.text(
            f"Code points {model.offset:,}–"
            f"{min(model.length, model.offset + 4096):,} / {model.length:,}"
        )
        if imgui.button("Previous text"):
            model.page(-1)
        imgui.same_line()
        if imgui.button("Next text"):
            model.page(1)
        if imgui.begin_child("value", (-1, 150), imgui.ChildFlags_.borders):
            imgui.text_wrapped(model.detail)
        imgui.end_child()


class ObjectBrowser(SourceBrowser):
    def __init__(
        self, model: ObjectController, open_records: Callable[[], object]
    ) -> None:
        self.model = model
        super().__init__(
            "objects",
            (
                ObjectDetail(model),
                ObjectListing(model),
                CommandButton(
                    "records",
                    "Open records as table",
                    open_records,
                    lambda: bool(model.selected and model.selected.kind == "array"),
                ),
            ),
        )

    @property
    def available(self) -> bool:
        return self.model.root is not None

    def render(self, frame: FrameContext) -> None:
        if imgui.button("Root"):
            self.model.choose(())
        imgui.same_line()
        if imgui.button("Parent"):
            self.model.choose(self.model.navigation.path[:-1])
        _, self.model.as_text = imgui.checkbox(
            "Read records as text", self.model.as_text
        )
        super().render(frame)
        imgui.text_wrapped(self.model.navigation.message)


class MemberListing(Component):
    def __init__(
        self, model: NumericSourceController, select: Callable[[str], None]
    ) -> None:
        super().__init__("members")
        self.model, self.select = model, select

    def render(self, frame: FrameContext) -> None:
        if imgui.begin_child("members", (-1, 220), imgui.ChildFlags_.borders):
            clipper = imgui.ListClipper()
            clipper.begin(len(self.model.entries))
            while clipper.step():
                for entry in self.model.entries[
                    clipper.display_start : clipper.display_end
                ]:
                    if imgui.selectable(
                        label_text(entry.name) + "###" + entry.name,
                        entry.name == self.model.settings.member,
                    )[0]:
                        self.select(entry.name)
                    target(frame.child(entry.name), "select")
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(
                            f"{entry.dtype} {entry.shape} · {entry.bytes:,} bytes\n"
                            f"{entry.diagnostic}"
                        )
        imgui.end_child()


class NumericBrowser(SourceBrowser):
    def __init__(
        self,
        key: str,
        model: NumericSourceController,
        select: Callable[[str], None],
        mapping: Component | None = None,
    ) -> None:
        self.model = model
        super().__init__(
            key, (MemberListing(model, select), *((mapping,) if mapping else ()))
        )

    @property
    def available(self) -> bool:
        return self.model.catalog is not None

    def render(self, frame: FrameContext) -> None:
        imgui.text(f"{len(self.model.entries):,} members · metadata first")
        super().render(frame)
        entry = self.model.entry
        if entry:
            imgui.text_wrapped(f"{entry.name}: {entry.dtype} {entry.shape}")
            imgui.text(f"Original storage: {entry.bytes:,} bytes")
            if entry.diagnostic:
                imgui.text_wrapped(entry.diagnostic)


class SourceRouter(Container):
    def __init__(self, browsers: tuple[SourceBrowser, ...]) -> None:
        super().__init__("browser", ())
        self.browsers = browsers

    def render(self, frame: FrameContext) -> None:
        self.children = tuple(browser for browser in self.browsers if browser.available)
        super().render(frame)

    def close(self) -> None:
        for browser in self.browsers:
            browser.close()
