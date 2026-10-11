"""Explicit assembly is the only GUI layer that knows application controllers."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from datelier.analysis.types import Algorithm
from datelier.application.exploration import ProfileFamily
from datelier.application.sessions import EditorController, FileController
from datelier.gui.analysis import AnalysisSettingsView
from datelier.gui.comparisons.assembly import CompareComponents
from datelier.gui.components.layout import Component, Group, SharedView
from datelier.gui.components.layout.routing import RoutedContent
from datelier.gui.components.layout.viewport import ResizableViewport
from datelier.gui.context.audio import AudioProfileSettings
from datelier.gui.context.images import ImageProfileSettings
from datelier.gui.context.profiles import ProfileSettings
from datelier.gui.context.relationships import CorrelationSettings, RelationshipSettings
from datelier.gui.context.text.profiles import TextProfileSettings
from datelier.gui.context.transforms import HistoryView, TransformSettings
from datelier.gui.profiles.content import ProfileRouter
from datelier.gui.profiles.media import (
    AudioProfileContent,
    ImageProfileContent,
    TextProfileContent,
)
from datelier.gui.references.cache import PreviewTextures
from datelier.gui.references.preview import (
    GalleryReferencePreview,
    ReferenceMappingPopup,
    TableReferencePreview,
)
from datelier.gui.relationships.categories import CategoryRouter
from datelier.gui.relationships.content import RelationshipContent
from datelier.gui.relationships.grid import CorrelationContent
from datelier.gui.relationships.scatter import ScatterRouter
from datelier.gui.shell.browser import Welcome
from datelier.gui.shell.commands import SourceState, SourceStatus
from datelier.gui.shell.composition.inspect import assemble_inspect
from datelier.gui.shell.layout import CanvasTabs, NamedTab
from datelier.gui.sources.columns import ColumnCatalog
from datelier.gui.sources.imports import ImportSettings
from datelier.gui.table import TableView
from datelier.io.jobs import LoadPhase
from datelier.plotting.relationships import Relationships
from datelier.plotting.scatter import Scatter


@dataclass
class FileComponents:
    source: Component
    canvas: Component
    context: Component
    table: Component
    columns: Component
    previews: PreviewTextures

    def prepare(self) -> None:
        self.previews.prepare()

    def close(self) -> None:
        for component in (
            self.source,
            self.canvas,
            self.context,
            self.table,
            self.columns,
        ):
            component.close()
        self.previews.clear()


def assemble_file(
    file: FileController,
    editor: EditorController,
    compare: CompareComponents,
    open_files: Callable[[], None],
    open_workspace: Callable[[], None],
) -> FileComponents:
    def points() -> Scatter | None:
        dashboard = file.explorer.active
        if file.analysis.source is not None:
            return file.analysis.plots.active
        return dashboard.scatters[0] if dashboard and dashboard.scatters else None

    def relationships() -> Relationships | None:
        dashboard = file.explorer.active
        return (
            dashboard.relationships
            if dashboard and file.plots.relationship_features
            else None
        )

    def pair(x: str, y: str | None) -> None:
        if y is None:
            file.profiles.choose((x,))
            editor.choose_route("Profiles")
        elif x in file.plots.numeric and y in file.plots.numeric:
            file.analysis.choose_source(None)
            file.plots.choose_chart("Scatter 2D")
            file.plots.choose_axis("x_index", file.plots.numeric.index(x))
            file.plots.choose_axis("y_index", file.plots.numeric.index(y))
            file.plots.custom_scatter = True
            editor.choose_route("Relationships")

    def route() -> str:
        return "Compare files" if editor.navigation.comparing else file.views.tab

    def open_result(algorithm: Algorithm) -> None:
        file.open_analysis_result(algorithm)
        editor.choose_route("Relationships")

    def write_category_height(value: float) -> None:
        file.views = replace(file.views, category_height=value)

    height_writers = {
        "Scatter 2D": lambda value: setattr(
            file, "views", replace(file.views, scatter_height=value)
        ),
        "Scatter 3D": lambda value: setattr(
            file, "views", replace(file.views, scatter3d_height=value)
        ),
    }

    def scatter_viewport() -> ResizableViewport:
        return ResizableViewport(
            "scatter",
            RelationshipContent(
                ScatterRouter(
                    points,
                    file.selection,
                    file.table.go_to,
                    lambda: file.plots.scatter_dimensions,
                ),
                CategoryRouter(
                    lambda: (
                        file.explorer.active.category_chart
                        if file.explorer.active
                        else None
                    ),
                    file.selection,
                    file.table.go_to,
                ),
                lambda: file.plots.relationship_chart != "Scatter",
            ),
            read_height=lambda: {
                "Scatter 2D": file.views.scatter_height,
                "Scatter 3D": file.views.scatter3d_height,
            }.get(file.plots.chart_choice, file.views.category_height),
            write_height=lambda value: height_writers.get(
                file.plots.chart_choice, write_category_height
            )(value),
        )

    def correlation_viewport() -> ResizableViewport:
        return ResizableViewport(
            "correlations",
            CorrelationContent(
                relationships,
                file.selection,
                file.table.go_to,
                pair,
                lambda: file.views.relationship_mode,
            ),
            read_height=lambda: file.views.relationship_height,
            write_height=lambda value: setattr(
                file, "views", replace(file.views, relationship_height=value)
            ),
        )

    previews = PreviewTextures(file.references, lambda: file.gallery.scope)
    mapping_popup = ReferenceMappingPopup(file.reference_tools)

    def preview(column: str, value: str, label: str, extent: float) -> Component:
        return TableReferencePreview(
            file.reference_tools, previews, mapping_popup, column, value, label, extent
        )

    def gallery_preview(
        column: str, value: str, label: str, extent: float
    ) -> Component:
        return GalleryReferencePreview(
            file.reference_tools, previews, mapping_popup, column, value, label, extent
        )

    inspect = assemble_inspect(file, editor, gallery_preview, previews)

    def open_image_record(index: int) -> None:
        profile = file.images.profile_jobs.active
        active = file.inspection
        if (
            profile is None
            or active is None
            or profile.revision != active.dataset.revision
        ):
            return
        row = profile.records.row(index, named=True)
        position, row_id = int(row["position"]), int(row["row_id"])
        if not file.records.open_position(
            profile.revision,
            position,
            row_id,
            profile.settings.column if profile.mapping is None else "record_index",
            profile.mapping is not None,
        ):
            return
        file.table.go_to(position)
        editor.choose_route("Inspect")

    profile_content = RoutedContent(
        {
            ProfileFamily.COLUMNS: ProfileRouter(file.profiles),
            ProfileFamily.TEXT: TextProfileContent(file.text, file.profiles),
            ProfileFamily.AUDIO: AudioProfileContent(file.audio),
            ProfileFamily.IMAGES: ImageProfileContent(file.images, open_image_record),
        },
        lambda: file.profiles.family,
    )
    profile_settings = Group(
        "profile-context",
        (
            ProfileSettings(file.profiles, file.plots),
            RoutedContent(
                {
                    ProfileFamily.TEXT: TextProfileSettings(
                        file.text, lambda: file.profiles.selected[0]
                    ),
                    ProfileFamily.AUDIO: AudioProfileSettings(
                        file.audio, lambda: file.profiles.selected[0]
                    ),
                    ProfileFamily.IMAGES: ImageProfileSettings(
                        file.images, lambda: file.profiles.selected[0]
                    ),
                },
                lambda: file.profiles.family,
            ),
        ),
    )

    canvas = CanvasTabs(
        (
            NamedTab("Profiles", profile_content),
            NamedTab(
                "Relationships",
                scatter_viewport(),
            ),
            NamedTab(
                "Correlations",
                correlation_viewport(),
            ),
            NamedTab("Inspect", inspect.canvas),
            NamedTab("Compare files", SharedView(compare.canvas)),
        ),
        route,
        editor.choose_route,
    )
    canvas_content = RoutedContent(
        {
            "Welcome": Welcome(
                open_files,
                open_workspace,
                lambda: editor.preferences.value.recent,
                editor.open_recent,
            ),
            "Inspection": canvas,
        },
        lambda: (
            "Welcome"
            if (
                file.inspection is None
                and file.loader.status.phase == LoadPhase.IDLE
                and not editor.navigation.comparing
            )
            else "Inspection"
        ),
    )
    context = CanvasTabs(
        (
            NamedTab(
                "View",
                RoutedContent(
                    {
                        "Profiles": profile_settings,
                        "Relationships": Group(
                            "relationship-tools",
                            (
                                RelationshipSettings(
                                    file.plots,
                                    editor.choose_relationship_chart,
                                    file.analysis,
                                ),
                                AnalysisSettingsView(file.analysis, open_result),
                            ),
                        ),
                        "Correlations": CorrelationSettings(
                            file.plots,
                            lambda: file.views.relationship_mode,
                            lambda v: setattr(
                                file, "views", replace(file.views, relationship_mode=v)
                            ),
                        ),
                        "Inspect": inspect.settings,
                        "Compare files": SharedView(compare.settings),
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
        Group(
            "source-content",
            (
                source_status,
                ImportSettings(
                    file.imports,
                    lambda: file.loader.status.phase == LoadPhase.FAILED,
                    file.loader.abandon,
                ),
                inspect.browser,
            ),
        ),
        canvas_content,
        context,
        TableView(
            file.table,
            preview,
            file.reference_tools,
            lambda: (float(previews.retained_bytes), float(previews.uploads)),
        ),
        ColumnCatalog(file.schema),
        previews,
    )
