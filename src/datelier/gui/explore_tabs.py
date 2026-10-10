"""Exploration tab family: each tab renders only its immediate content views."""

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.core.dataset import Dataset
from datelier.gui.analysis.session import AnalysisSession
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.data.table import TableView
from datelier.gui.plots.controls import PlotControls
from datelier.gui.profiles.binding import ProfileMedia
from datelier.inspection.exploration import Dashboard, Explorer
from datelier.plotting.data import Scatter
from datelier.plotting.selection import LinkedSelection

if TYPE_CHECKING:
    from datelier.gui.exploration import ExplorationView
    from datelier.gui.file_session import FileSession


@dataclass(frozen=True)
class ExplorationBinding:
    explorer: Explorer
    selection: LinkedSelection
    table: TableView
    plots: PlotControls | None
    dataset: Dataset | None
    analysis: AnalysisSession | None
    owner: FileSession | None


class ExploreTab(BoundView[ExplorationBinding], ABC):
    label: str

    def __init__(self, state: ExplorationView) -> None:
        self.state = state


class ProfilesTab(ExploreTab):
    label = "Profiles"

    def draw(self, binding: ExplorationBinding, frame: FrameContext) -> None:
        b = binding
        dashboard = b.explorer.active
        self.show_profile(b.explorer, dashboard, b.dataset, b.owner)

    def show_profile(
        self,
        explorer: Explorer,
        dashboard: Dashboard | None,
        dataset: Dataset | None,
        owner: FileSession | None = None,
    ) -> None:
        if (
            self.state.profile.selection.columns is None
            and dashboard is not None
            and (dashboard.comparison is not None)
            and (self.state.comparison_mode < 5)
        ):
            self.state.profile.selection.columns = dashboard.settings.comparison.columns
            self.state.profile.mode = self.state.comparison_mode
            if not self.state.profile.area.height:
                self.state.profile.area.height = self.state.comparison_area.height
        media = (
            ProfileMedia(
                owner.text.jobs.settings.column,
                lambda: owner.images.show_mapped_profile(owner),
                lambda column: owner.images.show_profile(owner, column),
                lambda column: owner.text.show(owner, column),
            )
            if owner is not None
            else None
        )
        if self.state.profile.show(explorer, dashboard, dataset, media):
            self.state.plot_frames += 1


class RelationshipsTab(ExploreTab):
    label = "Relationships"

    def draw(self, binding: ExplorationBinding, frame: FrameContext) -> None:
        b = binding
        dashboard = b.explorer.active
        if dashboard is None:
            imgui.text_wrapped(b.explorer.message)
            if b.plots is not None and b.dataset is not None:
                if self.state.categories.controls(b.plots, b.explorer, b.dataset):
                    return
                if b.analysis is not None:
                    points = b.analysis.scatter_controls(b.dataset, b.plots, b.explorer)
                    if points is not None:
                        self.show_scatter(None, b.selection, b.table, points, b.plots)
            return
        self.show_relationship_charts(
            b.explorer, dashboard, b.selection, b.table, b.plots, b.dataset, b.analysis
        )

    def show_relationship_charts(
        self,
        explorer: Explorer,
        dashboard: Dashboard,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None,
        dataset: Dataset | None,
        analysis: AnalysisSession | None,
    ) -> None:
        if (
            plots is not None
            and dataset is not None
            and self.state.categories.controls(plots, explorer, dataset)
        ):
            chart = dashboard.category_chart
            if chart is not None and chart.settings == plots.category_settings():
                if self.state.categories.show(chart, selection, table):
                    self.state.plot_frames += 1
            else:
                imgui.text_wrapped(explorer.message)
            return
        self.show_scatter_controls(
            explorer, dashboard, selection, table, plots, dataset, analysis
        )

    def show_scatter_controls(
        self,
        explorer: Explorer,
        dashboard: Dashboard,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None,
        dataset: Dataset | None,
        analysis: AnalysisSession | None,
    ) -> None:
        if dashboard is not self.state._dashboard:
            self.state._dashboard = dashboard
            self.state.scatter_index = min(
                self.state.saved_scatter_index or 0, max(0, len(dashboard.scatters) - 1)
            )
            self.state.saved_scatter_index = None
            if plots is not None and dashboard.scatters:
                first = dashboard.scatters[self.state.scatter_index]
                plots.x_index = plots.numeric.index(first.x_name)
                plots.y_index = plots.numeric.index(first.y_name)
        points = None
        if analysis is not None and dataset is not None and (plots is not None):
            points = analysis.scatter_controls(dataset, plots, explorer)
            if analysis.source is not None and points is None:
                return
        if plots is not None and dataset is not None and (analysis is None):
            plots.show_axes(explorer, dataset)
        self.show_scatter(dashboard, selection, table, points, plots)

    def show_scatter(
        self,
        dashboard: Dashboard | None,
        selection: LinkedSelection,
        table: TableView,
        override: Scatter | None = None,
        plots: PlotControls | None = None,
    ) -> None:
        if override is None and (dashboard is None or not dashboard.scatters):
            imgui.text_wrapped(
                "No suitable automatic scatter: requires two numeric columns "
                "with finite, nonconstant pairs."
            )
            return
        if override is None:
            assert dashboard is not None
            names = [f"{p.x_name} / {p.y_name}" for p in dashboard.scatters]
            self.state.scatter_index = min(self.state.scatter_index, len(names) - 1)
            changed = False
            if plots is None:
                changed, self.state.scatter_index = imgui.combo(
                    "Suggested scatter", self.state.scatter_index, names
                )
            points = dashboard.scatters[self.state.scatter_index]
            if changed and plots is not None:
                plots.x_index = plots.numeric.index(points.x_name)
                plots.y_index = plots.numeric.index(points.y_name)
                plots.custom_scatter = True
        else:
            points = override
        three_d = plots.three_d if plots is not None else points.z is not None
        if self.state.scatter.show(
            points, selection, table, three_d, embedding=override is not None
        ):
            self.state.plot_frames += 1
            self.state.scatter_frames += 1


class CorrelationsTab(ExploreTab):
    label = "Correlations"

    def draw(self, binding: ExplorationBinding, frame: FrameContext) -> None:
        b = binding
        dashboard = b.explorer.active
        if dashboard is None:
            imgui.text_wrapped(b.explorer.message)
            if b.plots is not None and b.dataset is not None:
                self.state.relationships.controls(
                    len(
                        b.plots.relationship_features
                        or b.plots.numeric[: b.plots.correlation_columns]
                    ),
                    b.plots,
                    b.explorer,
                    b.dataset,
                )
            return
        self.show_correlations(
            b.explorer, dashboard, b.selection, b.table, b.plots, b.dataset, b.analysis
        )

    def show_correlations(
        self,
        explorer: Explorer,
        dashboard: Dashboard,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None,
        dataset: Dataset | None,
        analysis: AnalysisSession | None,
    ) -> None:
        if dashboard.relationships is None:
            return
        if plots is not None and dataset is not None:
            self.state.relationships.show_features(plots, explorer, dataset)
        action = self.state.relationships.show(
            dashboard.relationships, selection, table, plots, explorer, dataset
        )
        if action is not None and plots is not None and (dataset is not None):
            x, y = action
            if y is None:
                plots.profile_index = plots.columns.index(x) + 1
                self.state.profile_index = 0
                self.state.profile.selection.columns = (x,)
                self.state.comparison_mode = 5
                self.state.tab = "Profiles"
            else:
                plots.custom_scatter = True
                plots.three_d = False
                if analysis is not None:
                    analysis.source = None
                plots.x_index, plots.y_index = (
                    plots.numeric.index(x),
                    plots.numeric.index(y),
                )
                self.state.scatter_index = 0
                self.state.tab = "Relationships"
                plots.relationship_chart = "Scatter"
            explorer.request(dataset, plots.settings())


class InspectTab(ExploreTab):
    label = "Inspect"

    def draw(self, binding: ExplorationBinding, frame: FrameContext) -> None:
        if binding.owner is not None:
            owner = binding.owner
            owner.inspect.show(
                owner.references,
                owner.reference_view,
                binding.selection,
                binding.table,
                owner,
            )
