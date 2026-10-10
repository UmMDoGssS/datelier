"""Explicit assembly is the only GUI layer that knows application controllers."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from imgui_bundle import imgui

from datelier.analysis.types import Algorithm
from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.application.records import RecordKind
from datelier.gui.analysis.view import AnalysisSettingsView
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.context.history import HistoryView
from datelier.gui.context.media import InspectSettings
from datelier.gui.context.profiles import ProfileSettings
from datelier.gui.context.relationships import CorrelationSettings, RelationshipSettings
from datelier.gui.context.transforms import TransformSettings
from datelier.gui.profiles.content import ProfileRouter
from datelier.gui.records.audio import AudioContent
from datelier.gui.records.base import RecordContent
from datelier.gui.records.collection import RecordBody, RecordCollection
from datelier.gui.records.images import ImageContent
from datelier.gui.records.text import TextContent
from datelier.gui.relationships.correlations import CorrelationPlot
from datelier.gui.relationships.scatter import ScatterPlot
from datelier.gui.shell.navigation import CanvasTabs, NamedTab
from datelier.gui.shell.status import SourceState, SourceStatus
from datelier.gui.sources.columns import ColumnCatalog
from datelier.gui.table.view import TableView
from datelier.io.loading import LoadPhase
from datelier.plotting.data import Scatter
from datelier.plotting.relationships import Relationships


class Message(Component):
    def __init__(self, key: str, text: str) -> None:
        super().__init__(key)
        self.text = text

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.text)


class ContextRoutes(Container):
    def __init__(
        self, routes: dict[str, Component], selected: Callable[[], str]
    ) -> None:
        super().__init__("view", ())
        self.routes = routes
        self.selected = selected

    def render(self, frame: FrameContext) -> None:
        # Assembly supplies the navigation provider explicitly.
        route = self.selected()
        child = self.routes.get(route)
        self.children = (child,) if child else ()
        super().render(frame)


@dataclass
class FileComponents:
    source: Component
    canvas: Component
    context: Component
    table: Component

    def close(self) -> None:
        for component in (self.source, self.canvas, self.context, self.table):
            component.close()


def assemble_file(file: FileController, editor: EditorController) -> FileComponents:
    def points() -> Scatter | None:
        dashboard = file.explorer.active
        if file.analysis.source is not None:
            return file.analysis.plots.active
        return dashboard.scatters[0] if dashboard and dashboard.scatters else None

    def relationships() -> Relationships | None:
        dashboard = file.explorer.active
        return dashboard.relationships if dashboard else None

    def pair(x: str, y: str | None) -> None:
        if y is None:
            file.profiles.choose((x,))
            editor.choose_route("Profiles")
        else:
            file.plots.choose_axis("x_index", file.plots.numeric.index(x))
            file.plots.choose_axis("y_index", file.plots.numeric.index(y))
            file.plots.custom_scatter = True
            editor.choose_route("Relationships")

    def route() -> str:
        return "Compare files" if editor.navigation.comparing else file.views.tab

    def open_result(algorithm: Algorithm) -> None:
        file.open_analysis_result(algorithm)
        editor.choose_route("Relationships")

    def scatter_viewport() -> ResizableViewport:
        return ResizableViewport(
            "scatter",
            ScatterPlot(points, file.selection, file.table.go_to),
            read_height=lambda: file.views.scatter_height,
            write_height=lambda value: setattr(
                file, "views", replace(file.views, scatter_height=value)
            ),
        )

    def correlation_viewport() -> ResizableViewport:
        return ResizableViewport(
            "correlations",
            CorrelationPlot(relationships, pair),
            read_height=lambda: file.views.relationship_height,
            write_height=lambda value: setattr(
                file, "views", replace(file.views, relationship_height=value)
            ),
        )

    def record_viewport(kind: RecordKind, content: RecordContent) -> ResizableViewport:
        if kind == RecordKind.IMAGE:
            return ResizableViewport(
                "image-viewport",
                content,
                minimum=100,
                read_height=lambda: file.views.image_height,
                write_height=lambda value: setattr(
                    file, "views", replace(file.views, image_height=value)
                ),
            )
        if kind == RecordKind.AUDIO:
            return ResizableViewport(
                "audio-viewport",
                content,
                read_height=lambda: file.audio.settings.plot_height,
                write_height=lambda value: setattr(
                    file.audio,
                    "settings",
                    replace(file.audio.settings, plot_height=value),
                ),
            )
        return ResizableViewport(kind.value, content, height=220, minimum=100)

    body = RecordBody(
        file.records,
        file.references,
        {
            RecordKind.IMAGE: ImageContent(file.images),
            RecordKind.TEXT: TextContent(file.text),
            RecordKind.AUDIO: AudioContent(file.audio),
        },
        record_viewport,
    )
    records = RecordCollection(file.records, body, file.table.go_to)

    canvas = CanvasTabs(
        (
            NamedTab("Profiles", ProfileRouter(file.profiles)),
            NamedTab(
                "Relationships",
                scatter_viewport(),
            ),
            NamedTab(
                "Correlations",
                correlation_viewport(),
            ),
            NamedTab("Inspect", records),
            NamedTab(
                "Compare files", Message("comparisons", "Choose sources to compare.")
            ),
        ),
        route,
        editor.choose_route,
    )
    context = CanvasTabs(
        (
            NamedTab(
                "View",
                ContextRoutes(
                    {
                        "Profiles": ProfileSettings(file.profiles, file.plots),
                        "Relationships": Container(
                            "relationship-tools",
                            (
                                RelationshipSettings(file.plots),
                                AnalysisSettingsView(file.analysis, open_result),
                            ),
                        ),
                        "Correlations": CorrelationSettings(file.plots),
                        "Inspect": InspectSettings(
                            file.records, file.text, file.images, file.audio
                        ),
                    },
                    route,
                ),
            ),
            NamedTab(
                "Transform",
                TransformSettings(lambda: file.choices, file.editor),
                lambda: not editor.navigation.comparing,
            ),
            NamedTab(
                "History",
                HistoryView(file.editor),
                lambda: not editor.navigation.comparing,
            ),
        ),
        lambda: editor.navigation.context_tab,
        lambda name: setattr(editor.navigation, "context_tab", name),
    )
    source_status = SourceStatus(
        lambda: SourceState(
            file.title,
            file.loader.status.message,
            file.loader.status.phase == LoadPhase.LOADING,
            file.recovery is not None,
            bool(file.recovery and file.recovery.deferred),
        ),
        lambda path, accept, prepare: editor.recover(
            file.identity, path, accept, prepare
        ),
    )
    return FileComponents(
        Container("source-content", (source_status, ColumnCatalog(file.schema))),
        canvas,
        context,
        TableView(file.table),
    )
