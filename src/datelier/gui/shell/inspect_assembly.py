"""Assemble source browsers and Inspect families from narrow dependencies."""

from dataclasses import dataclass, replace

from datelier.application.annotations.navigation import open_rows
from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.application.records import RecordKind
from datelier.gui.components.base import Component, Group
from datelier.gui.components.routing import RoutedContent
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.context.mapping import MappingSettings
from datelier.gui.context.media import InspectSettings
from datelier.gui.context.slices import SliceSettingsView
from datelier.gui.records.arrays import ArrayContent
from datelier.gui.records.audio import AudioContent
from datelier.gui.records.base import RecordContent
from datelier.gui.records.collection import RecordBody, RecordCollection
from datelier.gui.records.images import ImageContent
from datelier.gui.records.text import TextContent
from datelier.gui.records.textures import TextureCache
from datelier.gui.records.values import GalleryContent
from datelier.gui.sources.browser import NumericBrowser, ObjectBrowser, SourceRouter
from datelier.gui.sources.numeric import NumericContent
from datelier.gui.sources.routing import SourceInspection
from datelier.gui.sources.views import RecordViewSelector
from datelier.gui.table.cells import ReferenceFactory
from datelier.inspection.annotations.association_types import AssociatedBox


@dataclass
class InspectComponents:
    canvas: Component
    settings: Component
    browser: Component


def assemble_inspect(
    file: FileController,
    editor: EditorController,
    preview: ReferenceFactory,
    textures: TextureCache,
) -> InspectComponents:
    viewport_factories = {
        RecordKind.IMAGE: lambda content: ResizableViewport(
            "image-viewport",
            content,
            minimum=100,
            read_height=lambda: file.views.image_height,
            write_height=lambda value: setattr(
                file, "views", replace(file.views, image_height=value)
            ),
        ),
        RecordKind.AUDIO: lambda content: ResizableViewport(
            "audio-viewport",
            content,
            read_height=lambda: file.audio.settings.plot_height,
            write_height=lambda value: setattr(
                file.audio, "settings", replace(file.audio.settings, plot_height=value)
            ),
        ),
    }

    def record_viewport(kind: RecordKind, content: RecordContent) -> ResizableViewport:
        factory = viewport_factories.get(kind)
        return (
            factory(content)
            if factory
            else ResizableViewport(kind.value, content, height=220, minimum=100)
        )

    def annotation_rows(rows: tuple[int, ...]) -> None:
        prepared = file.images.annotations.active
        if prepared and open_rows(
            file.records, prepared, file.identity, file.view_name, rows
        ):
            editor.choose_route("Inspect")

    def annotation_box(box: AssociatedBox) -> None:
        prepared = file.images.annotations.active
        if prepared and box in prepared.by_image.get(box.origin, ()):
            annotation_rows((box.origin.row_id,))
            file.images.annotation_tools.selected = box

    body = RecordBody(
        file.records,
        GalleryContent(preview, file.gallery, textures),
        {
            RecordKind.IMAGE: ImageContent(
                file.images, annotation_rows, annotation_box
            ),
            RecordKind.TEXT: TextContent(file.text),
            RecordKind.AUDIO: AudioContent(file.audio),
            RecordKind.ARRAY: ArrayContent(
                file.array_records, file.array_record_source
            ),
        },
        record_viewport,
    )
    records = RecordCollection(file.records, body, file.table.go_to)

    sources = {"Array": file.array_source, "Tensor": file.tensor_source}

    def source_mode() -> str:
        return next(
            (
                name
                for name, source in sources.items()
                if source.catalog and source.member_mode
            ),
            "",
        )

    def record_mode() -> None:
        for source in sources.values():
            source.member_mode = False

    def select_member(name: str, source: str = "Array") -> None:
        sources[source].choose(name)
        editor.choose_route("Inspect")

    inspect = SourceInspection(
        records,
        {
            "Array": NumericContent(file.array_source),
            "Tensor": NumericContent(file.tensor_source),
        },
        source_mode,
        record_mode,
    )
    media_settings = InspectSettings(file.records, file.text, file.images, file.audio)
    record_settings = RoutedContent(
        {
            "Array": SliceSettingsView(file.array_record_source, file.array_records),
            "": media_settings,
        },
        lambda: "Array" if file.records.current_kind() == RecordKind.ARRAY else "",
    )
    inspect_settings = RoutedContent(
        {
            "Array": SliceSettingsView(file.array_source),
            "Tensor": SliceSettingsView(file.tensor_source),
            "": record_settings,
        },
        source_mode,
    )
    browser = SourceRouter(
        (
            ObjectBrowser(
                file.objects,
                lambda: file.record_views.open(
                    file, file.record_views.path, as_text=file.objects.as_text
                ),
            ),
            NumericBrowser(
                "arrays",
                file.array_source,
                select_member,
                MappingSettings(
                    file.array_source,
                    lambda mapping: file.record_views.open_array(file, mapping),
                ),
            ),
            NumericBrowser(
                "tensors",
                file.tensor_source,
                lambda name: select_member(name, "Tensor"),
            ),
        )
    )
    record_views = RecordViewSelector(
        lambda: (
            (None, "Source"),
            *((view.identity, view.title) for view in file.record_views.files),
        ),
        lambda: file.record_views.active_id,
        lambda identity: setattr(file.record_views, "active_id", identity),
        file.record_views.close_view,
    )

    return InspectComponents(
        inspect, inspect_settings, Group("source-tools", (browser, record_views))
    )
