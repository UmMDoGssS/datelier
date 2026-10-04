"""Docked exploration dashboard; renders bounded, prepared values."""

from dataclasses import dataclass, field

from imgui_bundle import imgui, implot

from datelier.dataset import DatasetRevision
from datelier.exploration import Dashboard, Explorer
from datelier.gui_selection import ScatterInteraction
from datelier.gui_table import TableView
from datelier.plotting import CORRELATION_ROW_LIMIT
from datelier.selection import LinkedSelection


@dataclass
class ExplorationView:
    profile_index: int = 0
    scatter_index: int = 0
    plot_frames: int = 0
    scatter_frames: int = 0
    dock_id: int = 0
    tab: str = "Profiles"
    interaction: ScatterInteraction = field(default_factory=ScatterInteraction)
    fit: bool = False
    _scatter_key: tuple[DatasetRevision, str, str] | None = None
    _profile_key: tuple[DatasetRevision, str, int, int] | None = None

    def show(
        self, explorer: Explorer, selection: LinkedSelection, table: TableView
    ) -> None:
        self.dock_id = imgui.get_window_dock_id()
        imgui.text_wrapped(explorer.message)
        dashboard = explorer.active
        if dashboard is None:
            return
        profiles = dashboard.profiles
        imgui.text(f"{profiles.row_count:,} rows · {profiles.total_columns} columns")
        if imgui.begin_tab_bar("Exploration views"):
            for label, callback in (
                ("Profiles", self.show_profile),
                (
                    "Scatter",
                    lambda dashboard: self.show_scatter(dashboard, selection, table),
                ),
                ("Correlations", self.show_correlations),
            ):
                flags = imgui.TabItemFlags_.set_selected if self.tab == label else 0
                opened, _ = imgui.begin_tab_item(label, flags=flags)
                if opened:
                    callback(dashboard)
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        self.tab = ""  # One-shot selection; subsequent mouse tab choices persist.

    def show_profile(self, dashboard: Dashboard) -> None:
        profiles = dashboard.profiles
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

    def show_correlations(self, dashboard: Dashboard) -> None:
        imgui.text_wrapped(
            f"Pearson correlations: first {dashboard.settings.correlation_columns} "
            f"numeric columns, at most {CORRELATION_ROW_LIMIT:,} evenly spaced rows; "
            "pairwise finite values. Constant / insufficient pairs are undefined."
        )
        if not dashboard.correlations:
            imgui.text("At least two numeric columns are required.")
        for correlation in dashboard.correlations:
            value = (
                f"{correlation.value:.4f}"
                if correlation.value is not None
                else "undefined"
            )
            imgui.text_wrapped(
                f"{correlation.x_name} / {correlation.y_name}: {value} "
                f"· {correlation.finite_pairs:,} finite pairs"
            )

    def show_scatter(
        self, dashboard: Dashboard, selection: LinkedSelection, table: TableView
    ) -> None:
        if not dashboard.scatters:
            imgui.text_wrapped(
                "No suitable automatic scatter: requires two numeric columns "
                "with finite, nonconstant pairs."
            )
            return
        names = [f"{p.x_name} / {p.y_name}" for p in dashboard.scatters]
        self.scatter_index = min(self.scatter_index, len(names) - 1)
        _, self.scatter_index = imgui.combo(
            "Suggested scatter", self.scatter_index, names
        )
        points = dashboard.scatters[self.scatter_index]
        imgui.text_wrapped(
            f"{len(points.x):,} evenly spaced points of {points.eligible_rows:,} "
            f"finite pairs ({points.total_rows:,} rows). "
            + (
                "Sampled."
                if len(points.x) < points.eligible_rows
                else "All eligible rows."
            )
        )
        imgui.text_wrapped(
            "Wheel: zoom · middle-drag: pan · double-click: fit. "
            "Click: select · Ctrl-click: toggle · Shift-drag: brush displayed points."
        )
        imgui.text_wrapped(selection.message)
        if imgui.button("Clear selection"):
            selection.choose(dashboard.revision, ())
        imgui.same_line()
        if imgui.button("Fit scatter"):
            self.fit = True
        key = (points.revision, points.x_name, points.y_name)
        if key != self._scatter_key:
            self.fit = True
            self._scatter_key = key
        if self.fit:
            implot.set_next_axes_to_fit()
            self.fit = False
        style = implot.Spec()
        style.marker_size = 2
        style.line_weight = 0
        height = max(150, min(220, imgui.get_content_region_avail().y - 5))
        if implot.begin_plot("Scatter", (-1, height)):
            implot.setup_axes(points.x_name, points.y_name)
            implot.plot_scatter("Rows", points.x, points.y, style)
            self.interaction.show(points, selection, table)
            implot.end_plot()
            self.plot_frames += 1
            self.scatter_frames += 1
