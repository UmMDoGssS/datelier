"""Docked exploration dashboard; renders bounded, prepared values."""

from dataclasses import dataclass, field

from imgui_bundle import imgui, implot

from datelier.dataset import Dataset, DatasetRevision
from datelier.exploration import Dashboard, Explorer
from datelier.gui_analysis import AnalysisSession
from datelier.gui_distributions import MODES, show_comparison
from datelier.gui_plot_controls import PlotControls
from datelier.gui_relationships import RelationshipView
from datelier.gui_scatter import draw_scatter
from datelier.gui_scatter3d import Scatter3DView
from datelier.gui_selection import ScatterInteraction
from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.selection import LinkedSelection


@dataclass
class ExplorationView:
    profile_index: int = 0
    comparison_mode: int = 0
    relationships: RelationshipView = field(default_factory=RelationshipView)
    _comparison_key: tuple[DatasetRevision, int, object] | None = None
    scatter_index: int = 0
    plot_frames: int = 0
    scatter_frames: int = 0
    scatter3d: Scatter3DView = field(default_factory=Scatter3DView)
    dock_id: int = 0
    tab: str = "Profiles"
    active_tab: str = "Profiles"
    saved_scatter_index: int | None = None
    interaction: ScatterInteraction = field(default_factory=ScatterInteraction)
    fit: bool = False
    _dashboard: Dashboard | None = None
    _scatter_key: tuple[DatasetRevision, str, str, str, bool] | None = None
    _profile_key: tuple[DatasetRevision, str, int, int] | None = None

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
        imgui.text_wrapped(explorer.message)
        dashboard = explorer.active
        if dashboard is None:
            if plots is not None and dataset is not None:
                plots.show_axes(explorer, dataset)
                if analysis is not None:
                    points = analysis.scatter_controls(dataset, plots)
                    if points is not None:
                        self.show_scatter(None, selection, table, points, plots)
            return
        profiles = dashboard.profiles
        imgui.text(f"{profiles.row_count:,} rows · {profiles.total_columns} columns")
        requested_tab, self.tab = self.tab, ""
        if imgui.begin_tab_bar("Exploration views"):
            for label, callback in (
                ("Profiles", self.show_profile),
                (
                    "Scatter",
                    lambda dashboard: self.show_scatter_controls(
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

    def show_profile(self, dashboard: Dashboard) -> None:
        profiles = dashboard.profiles
        if dashboard.comparison is not None:
            _, self.comparison_mode = imgui.combo(
                "Numeric comparison",
                self.comparison_mode,
                [*MODES, "Individual profiles"],
            )
            if self.comparison_mode < 5:
                key = (dashboard.revision, self.comparison_mode, dashboard.settings)
                if show_comparison(
                    dashboard.comparison,
                    self.comparison_mode,
                    key != self._comparison_key,
                ):
                    self.plot_frames += 1
                self._comparison_key = key
                if not imgui.collapsing_header("Individual column details"):
                    return
        imgui.text_wrapped(
            f"Profile focus: {dashboard.settings.profile_column}"
            if dashboard.settings.profile_column
            else (
                f"Profiles: first {len(profiles.columns)} "
                f"of {profiles.total_columns} columns."
            )
        )
        if not profiles.columns:
            return
        names = [p.name for p in profiles.columns]
        self.profile_index = min(self.profile_index, len(names) - 1)
        _, self.profile_index = imgui.combo("Profile column", self.profile_index, names)
        profile = profiles.columns[self.profile_index]
        bars = dashboard.bars[self.profile_index]
        imgui.text(f"{profile.kind} · {profile.dtype}")
        imgui.text(
            f"Nulls: {profile.null_count:,} · Nonfinite: {profile.nonfinite_count:,}"
        )
        if profile.minimum:
            imgui.text_wrapped(f"Range: {profile.minimum} to {profile.maximum}")
        if profile.mean is not None:
            imgui.text(f"Mean: {profile.mean:.6g}")
        if profile.distinct_count is not None:
            imgui.text(f"Distinct counted values: {profile.distinct_count:,}")
        imgui.text_wrapped(profile.note)
        key = (
            dashboard.revision,
            profile.name,
            dashboard.settings.bins,
            dashboard.settings.top_counts,
        )
        if key != self._profile_key:
            implot.set_next_axes_to_fit()
            self._profile_key = key
        if len(bars.counts) and implot.begin_plot("Distribution / counts", (-1, 170)):
            implot.setup_axes("Bin / category index", "Rows")
            implot.plot_bars("Rows", bars.positions, bars.counts, 0.8)
            implot.end_plot()
            self.plot_frames += 1
        if imgui.collapsing_header("Bin boundaries / category labels"):
            for i, (label, count) in enumerate(
                zip(bars.labels, bars.counts, strict=True)
            ):
                imgui.text_wrapped(f"{i}: {label} — {int(count):,}")

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
        action = self.relationships.show(dashboard.relationships, selection, table)
        if action is not None and plots is not None and dataset is not None:
            x, y = action
            if y is None:
                plots.profile_index = plots.columns.index(x) + 1
                self.profile_index = 0
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
                self.tab = "Scatter"
            explorer.request(dataset, plots.settings())

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
        if plots is not None and dataset is not None:
            plots.show_axes(explorer, dataset)
        points = None
        if analysis is not None and dataset is not None and plots is not None:
            points = analysis.scatter_controls(dataset, plots)
            if analysis.source is not None and points is None:
                return
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
        imgui.text_wrapped(
            f"{len(points.x):,} evenly spaced points of {points.eligible_rows:,} "
            f"finite rows ({points.total_rows:,} rows). "
            + (
                "Sampled."
                if len(points.x) < points.eligible_rows
                else "All eligible rows."
            )
        )
        if points.colors is not None:
            imgui.text_wrapped(points.colors.name + ": " + points.colors.note)
            if imgui.collapsing_header("Color legend"):
                for label, rgba in points.colors.legend:
                    color = imgui.ImVec4(
                        (rgba & 255) / 255,
                        ((rgba >> 8) & 255) / 255,
                        ((rgba >> 16) & 255) / 255,
                        1,
                    )
                    imgui.text_colored(color, label)
                    imgui.same_line()
                imgui.new_line()
        imgui.text_wrapped(selection.message)
        if imgui.button("Clear selection"):
            selection.choose(points.revision, ())
        imgui.same_line()
        if imgui.button("Fit scatter"):
            self.fit = True
        key = (
            points.revision,
            points.x_name,
            points.y_name,
            points.z_name,
            plots.three_d if plots is not None else False,
        )
        if key != self._scatter_key:
            self.fit = True
            self._scatter_key = key
        shown = (
            self.scatter3d.show(points, selection, table, self.fit)
            if plots is not None and plots.three_d
            else draw_scatter(points, selection, table, self.interaction, self.fit)
        )
        if shown:
            self.fit = False
            self.plot_frames += 1
            self.scatter_frames += 1
        if imgui.collapsing_header("Scatter gestures"):
            if plots is not None and plots.three_d:
                imgui.text_wrapped(
                    "3D: left-drag rotates, right-drag pans, wheel zooms. "
                    "Click selects; Ctrl-click toggles; "
                    "Shift-drag brushes projected displayed points."
                )
            imgui.text_wrapped(
                "2D wheel: zoom · middle-drag: pan · double-click: fit. "
                "Click: select · Ctrl-click: toggle · "
                "Shift-drag: brush displayed points."
            )
