"""Explicit assembly is the only GUI layer that knows application controllers."""

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.gui.analysis.view import AnalysisSettingsView
from datelier.gui.components.actions import JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext, Page
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.context.history import HistoryView
from datelier.gui.context.profiles import ProfileSettings
from datelier.gui.context.relationships import CorrelationSettings, RelationshipSettings
from datelier.gui.context.transforms import TransformSettings
from datelier.gui.profiles.content import ProfileRouter
from datelier.gui.relationships.correlations import CorrelationPlot
from datelier.gui.relationships.scatter import ScatterPlot
from datelier.gui.shell.docking import DockHost, DockPanel
from datelier.gui.shell.export import ExportDialog, ExportPort
from datelier.gui.shell.menu import MenuBar, OpenDialog
from datelier.gui.shell.navigation import CanvasTabs, FileTab, FileTabs, NamedTab
from datelier.gui.sources.columns import ColumnCatalog
from datelier.gui.table.view import TableView
from datelier.pipeline.editing import HistoryAction
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

    canvas = CanvasTabs(
        (
            NamedTab("Profiles", ProfileRouter(file.profiles)),
            NamedTab(
                "Relationships",
                ResizableViewport(
                    "scatter", ScatterPlot(points, file.selection, file.table.go_to)
                ),
            ),
            NamedTab(
                "Correlations",
                ResizableViewport("correlations", CorrelationPlot(relationships, pair)),
            ),
            NamedTab("Inspect", Message("records", "Choose records to inspect.")),
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
    return FileComponents(
        ColumnCatalog(file.schema), canvas, context, TableView(file.table)
    )


class WorkbenchPage(Page):
    def __init__(self, editor: EditorController, probe: GuiProbe) -> None:
        self.editor, self.probe = editor, probe
        self.files: dict[str, FileComponents] = {}
        empty = Message("empty", "Open a source to inspect data.")
        self.host = DockHost(
            DockPanel("source", "Source browser", empty),
            DockPanel("canvas", "Explore", empty),
            DockPanel("context", "Context", empty),
            DockPanel("table", "Table preview", empty),
        )
        self.open_dialog = OpenDialog(editor.open_paths)

        def capture_export() -> ExportPort | None:
            file = editor.active
            active = file.inspection
            if active is None:
                return None
            return ExportPort(
                file.title,
                lambda path, format, overwrite: file.exporter.request(
                    active.dataset,
                    path,
                    format,
                    overwrite=overwrite,
                    sources=tuple(
                        f.inspection.dataset.source.path
                        for f in editor.files
                        if f.inspection is not None
                    ),
                ),
                lambda: JobSnapshot(file.exporter.message, file.exporter.busy),
            )

        self.export_dialog = ExportDialog(capture_export)
        self.menu = MenuBar(
            lambda: setattr(self.open_dialog, "requested", True),
            lambda: setattr(self.host, "reset", True),
            lambda: setattr(hello_imgui.get_runner_params(), "app_shall_exit", True),
            lambda: setattr(self.export_dialog, "requested", True),
        )
        tabs = FileTabs(
            lambda: tuple(
                FileTab(f.identity, f.title, f.identity == editor.active_id)
                for f in editor.files
            ),
            editor.activate,
            editor.close_file,
            editor.new_file,
            lambda: self._history(HistoryAction.UNDO),
            lambda: self._history(HistoryAction.REDO),
            self.host.toggle_context,
            self.host.toggle_table,
        )
        super().__init__(
            "page", (tabs, self.host, self.open_dialog, self.export_dialog)
        )

    def _history(self, action: HistoryAction) -> None:
        if (
            not self.editor.navigation.comparing
            and self.editor.active.editor.pipeline
            and not self.editor.active.editor.busy
        ):
            self.editor.active.editor.request(action)

    def prepare(self) -> FrameContext:
        known = {f.identity for f in self.editor.files}
        for identity in set(self.files) - known:
            self.files.pop(identity).close()
        for file in self.editor.files:
            if file.identity not in self.files:
                self.files[file.identity] = assemble_file(file, self.editor)
        file = self.editor.active
        components = self.files[file.identity]
        for panel, content in (
            (self.host.source, components.source),
            (self.host.canvas, components.canvas),
            (self.host.context, components.context),
            (self.host.table, components.table),
        ):
            panel.children = (content,)
        return FrameContext(
            ViewScope(file.identity, file.view_name, file.loader.revision), self.probe
        )

    def close(self) -> None:
        for components in self.files.values():
            components.close()
        self.files.clear()
