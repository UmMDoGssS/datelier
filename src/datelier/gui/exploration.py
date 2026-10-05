"""Docked exploration dashboard; renders bounded, prepared values."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.core.dataset import Dataset
from datelier.gui.analysis.session import AnalysisSession
from datelier.gui.data.table import TableView
from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.categories import CategoryView
from datelier.gui.plots.controls import PlotControls
from datelier.gui.plots.relationships import RelationshipView
from datelier.gui.plots.scatter import ScatterView
from datelier.gui.plots.scatter3d import Scatter3DView
from datelier.gui.plots.selection import ScatterInteraction
from datelier.gui.profiles.view import ProfileView
from datelier.inspection.exploration import Dashboard, Explorer
from datelier.plotting.data import Scatter
from datelier.plotting.selection import LinkedSelection


@dataclass
class ExplorationView:
    profile: ProfileView = field(default_factory=ProfileView)
    comparison_area: PlotArea = field(default_factory=PlotArea)
    scatter: ScatterView = field(default_factory=ScatterView)
    comparison_mode: int = 0
    relationships: RelationshipView = field(default_factory=RelationshipView)
    scatter_index: int = 0
    plot_frames: int = 0
    scatter_frames: int = 0
    dock_id: int = 0
    tab: str = "Profiles"
    active_tab: str = "Profiles"
    saved_scatter_index: int | None = None
    _dashboard: Dashboard | None = None
    categories: CategoryView = field(default_factory=CategoryView)

    @property
    def scatter_area(self) -> PlotArea:
        return self.scatter.area

    @property
    def scatter3d_area(self) -> PlotArea:
        return self.scatter.area3d

    @property
    def scatter3d(self) -> Scatter3DView:
        return self.scatter.scatter3d

    @property
    def interaction(self) -> ScatterInteraction:
        return self.scatter.interaction

    @property
    def fit(self) -> bool:
        return self.scatter.fit

    @fit.setter
    def fit(self, value: bool) -> None:
        self.scatter.fit = value

    @property
    def profile_index(self) -> int:
        return self.profile.index

    @profile_index.setter
    def profile_index(self, value: int) -> None:
        if value != self.profile.index:
            self.profile.selection.columns = None
        self.profile.index = value

    @property
    def profile_mode(self) -> int:
        return self.profile.mode

    @profile_mode.setter
    def profile_mode(self, value: int) -> None:
        self.profile.mode = value

    def show(
        self,
        explorer: Explorer,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None = None,
        dataset: Dataset | None = None,
        analysis: AnalysisSession | None = None,
    ) -> None:
        self.dock_id = imgui.get_window_dock_id()
        dashboard = explorer.active
        if dashboard is None:
            imgui.text_wrapped(explorer.message)
            if plots is not None and dataset is not None:
                if self.active_tab == "Correlations":
                    self.relationships.controls(
                        len(
                            plots.relationship_features
                            or plots.numeric[: plots.correlation_columns]
                        ),
                        plots,
                        explorer,
                        dataset,
                    )
                    return
                if self.active_tab == "Profiles" and self.tab not in (
                    "Scatter",
                    "Relationships",
                ):
                    return
                if plots.relationship_chart != "Scatter":
                    self.categories.controls(plots, explorer, dataset)
                    return
                if analysis is not None:
                    points = analysis.scatter_controls(dataset, plots, explorer)
                    if points is not None:
                        self.show_scatter(None, selection, table, points, plots)
                else:
                    plots.show_axes(explorer, dataset)
            return
        profiles = dashboard.profiles
        imgui.text(f"{profiles.row_count:,} rows · {profiles.total_columns} columns")
        requested_tab, self.tab = self.tab, ""
        if requested_tab == "Scatter":
            requested_tab = "Relationships"
        if imgui.begin_tab_bar("Exploration views"):
            for label, callback in (
                (
                    "Profiles",
                    lambda dashboard: self.show_profile(explorer, dashboard, dataset),
                ),
                (
                    "Relationships",
                    lambda dashboard: self.show_relationship_charts(
                        explorer, dashboard, selection, table, plots, dataset, analysis
                    ),
                ),
                (
                    "Correlations",
                    lambda dashboard: self.show_correlations(
                        explorer, dashboard, selection, table, plots, dataset, analysis
                    ),
                ),
            ):
                flags = (
                    imgui.TabItemFlags_.set_selected if requested_tab == label else 0
                )
                opened, _ = imgui.begin_tab_item(label, flags=flags)
                if opened:
                    self.active_tab = label
                    callback(dashboard)
                    imgui.end_tab_item()
            imgui.end_tab_bar()

    def show_profile(
        self, explorer: Explorer, dashboard: Dashboard, dataset: Dataset | None
    ) -> None:
        if (
            self.profile.selection.columns is None
            and dashboard.comparison is not None
            and self.comparison_mode < 5
        ):
            self.profile.selection.columns = dashboard.settings.comparison.columns
            self.profile.mode = self.comparison_mode
            if not self.profile.area.height:
                self.profile.area.height = self.comparison_area.height
        if self.profile.show(explorer, dashboard, dataset):
            self.plot_frames += 1

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
            self.relationships.show_features(plots, explorer, dataset)
        action = self.relationships.show(
            dashboard.relationships, selection, table, plots, explorer, dataset
        )
        if action is not None and plots is not None and dataset is not None:
            x, y = action
            if y is None:
                plots.profile_index = plots.columns.index(x) + 1
                self.profile_index = 0
                self.profile.selection.columns = (x,)
                self.comparison_mode = 5
                self.tab = "Profiles"
            else:
                plots.custom_scatter = True
                plots.three_d = False
                if analysis is not None:
                    analysis.source = None
                plots.x_index, plots.y_index = (
                    plots.numeric.index(x),
                    plots.numeric.index(y),
                )
                self.scatter_index = 0
                self.tab = "Relationships"
                plots.relationship_chart = "Scatter"
            explorer.request(dataset, plots.settings())

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
            and self.categories.controls(plots, explorer, dataset)
        ):
            chart = dashboard.category_chart
            if chart is not None and chart.settings == plots.category_settings():
                if self.categories.show(chart, selection, table):
                    self.plot_frames += 1
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
        if dashboard is not self._dashboard:
            self._dashboard = dashboard
            self.scatter_index = min(
                self.saved_scatter_index or 0, max(0, len(dashboard.scatters) - 1)
            )
            self.saved_scatter_index = None
            if plots is not None and dashboard.scatters:
                first = dashboard.scatters[self.scatter_index]
                plots.x_index = plots.numeric.index(first.x_name)
                plots.y_index = plots.numeric.index(first.y_name)
        points = None
        if analysis is not None and dataset is not None and plots is not None:
            points = analysis.scatter_controls(dataset, plots, explorer)
            if analysis.source is not None and points is None:
                return
        if plots is not None and dataset is not None and analysis is None:
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
            self.scatter_index = min(self.scatter_index, len(names) - 1)
            changed = False
            if plots is None:
                changed, self.scatter_index = imgui.combo(
                    "Suggested scatter", self.scatter_index, names
                )
            points = dashboard.scatters[self.scatter_index]
            if changed and plots is not None:
                plots.x_index = plots.numeric.index(points.x_name)
                plots.y_index = plots.numeric.index(points.y_name)
                plots.custom_scatter = True
        else:
            points = override
        three_d = plots.three_d if plots is not None else points.z is not None
        if self.scatter.show(
            points, selection, table, three_d, embedding=override is not None
        ):
            self.plot_frames += 1
            self.scatter_frames += 1
