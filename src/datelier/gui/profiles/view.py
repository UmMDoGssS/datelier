"""Render prepared profiles in value space or with explicit category names."""

from dataclasses import dataclass, field, replace

import numpy as np
from imgui_bundle import imgui, implot

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.axes import AxisControls
from datelier.gui.plots.distributions import MODES, show_comparison
from datelier.gui.profiles.colors import profile_color
from datelier.gui.profiles.selector import show_selector
from datelier.gui.profiles.statistics import show_statistics, statistics_height
from datelier.inspection.exploration import Dashboard, Explorer
from datelier.inspection.profile_preview import ProfileRequest
from datelier.inspection.profile_selection import ProfileSelection
from datelier.inspection.profiles import COUNT_ROW_LIMIT, ColumnProfile, ProfileKind
from datelier.plotting.data import Bars


def profile_summary(profile: ColumnProfile, rows: int) -> str:
    counted = (
        f"{profile.counted_rows:,} counted (first {COUNT_ROW_LIMIT:,} rows)"
        if profile.kind == ProfileKind.CATEGORICAL and rows > COUNT_ROW_LIMIT
        else f"{profile.counted_rows:,} included"
    )
    percentage = profile.null_count / rows * 100 if rows else 0
    summary = f"{counted} · {profile.null_count:,} missing ({percentage:.1f}%)"
    if profile.nonfinite_count:
        summary += f" · {profile.nonfinite_count:,} nonfinite"
    return summary


@dataclass
class ProfileView:
    index: int = 0
    mode: int = 0
    area: PlotArea = field(default_factory=PlotArea)
    selection: ProfileSelection = field(default_factory=ProfileSelection)

    def show(
        self, explorer: Explorer, dashboard: Dashboard, dataset: Dataset | None
    ) -> bool:
        if dataset is None:
            return False
        automatic = dashboard.profiles.columns
        self.index = min(self.index, max(0, len(automatic) - 1))
        default = automatic[self.index].name if automatic else None
        self.selection.bind(dataset, default)
        if imgui.begin_table(
            "Profile controls", 2, imgui.TableFlags_.sizing_stretch_prop
        ):
            imgui.table_setup_column("Columns", init_width_or_weight=0.65)
            imgui.table_setup_column("Chart type", init_width_or_weight=0.35)
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.text("Columns")
            show_selector(self.selection)
            imgui.table_set_column_index(1)
            imgui.text("Chart type")
            selected = self.selection.columns or ()
            numeric = (
                bool(selected) and dataset.role(selected[0]).role == ColumnRole.NUMERIC
            )
            imgui.set_next_item_width(-1)
            if numeric:
                _, self.mode = imgui.combo("##Chart type", self.mode, MODES)
            else:
                imgui.begin_disabled()
                imgui.combo(
                    "##Chart type",
                    0,
                    [
                        "Counts"
                        if selected
                        and dataset.role(selected[0]).role == ColumnRole.CATEGORY
                        else "Histogram"
                    ],
                )
                imgui.end_disabled()
            imgui.end_table()
        selected = self.selection.columns or ()
        if not selected:
            explorer.profiles.clear()
            imgui.text("Choose columns to inspect.")
            return False
        request = ProfileRequest(
            replace(dashboard.settings.comparison, columns=selected),
            dashboard.settings.bins,
            dashboard.settings.top_counts,
        )
        explorer.profiles.ensure(dataset, request)
        group = explorer.profiles.active
        if group is None:
            imgui.text_wrapped(explorer.profiles.message)
            return False
        profiles = group.profiles.columns
        statistics_shown = False

        def footer() -> None:
            nonlocal statistics_shown
            statistics_shown = True
            show_statistics(profiles)

        numeric = profiles[0].kind == ProfileKind.NUMERIC
        if (
            profiles[0].kind == ProfileKind.CATEGORICAL
            and group.profiles.row_count > COUNT_ROW_LIMIT
        ):
            imgui.text(f"Counts and mode: first {COUNT_ROW_LIMIT:,} rows.")
        key = (dataset.revision, request, self.mode if numeric else 0)
        shown = False
        if (
            numeric
            and group.comparison is not None
            and any(p.counted_rows for p in profiles)
        ):
            prepared = group.comparison
            shown = self.area.show(
                "Profile plot",
                key,
                lambda height, fit, axes: show_comparison(
                    prepared,
                    self.mode,
                    fit,
                    title="##Profile distributions",
                    details=False,
                    height=height,
                    axes=axes,
                    colored=True,
                ),
                numeric_axes=(False, True) if self.mode in (3, 4) else (True, True),
                footer=footer,
                footer_height=statistics_height(len(profiles)),
            )
        elif (
            len(profiles) == 1
            and profiles[0].counted_rows
            and (not numeric or self.mode == 0)
        ):
            profile = profiles[0]
            shown = self.area.show(
                "Profile plot",
                key,
                lambda height, fit, axes: draw_profile(
                    profile, group.bars[0], height, axes, fit
                ),
                numeric_axes=(True, False)
                if profile.kind == ProfileKind.CATEGORICAL
                else (False, True)
                if profile.kind == ProfileKind.TEMPORAL
                else (True, True),
                footer=footer,
                footer_height=statistics_height(1),
            )
        else:
            imgui.text_wrapped(group.message or "No finite values to plot.")
        if not statistics_shown:
            footer()
        if imgui.collapsing_header("Details##profile"):
            if group.message:
                imgui.text_wrapped(group.message)
            for profile in profiles:
                imgui.text_wrapped(f"{profile.name}: " + profile.note)
            if group.comparison is not None and self.mode in (1, 2, 4):
                imgui.text_wrapped(
                    f"Curves use at most 2,000 finite values per column; "
                    f"seed {request.distribution.seed}, "
                    f"KDE bandwidth {request.distribution.bandwidth:g}."
                )
        return shown


def draw_histogram(name: str, bars: Bars, color: imgui.ImVec4 | None = None) -> None:
    """Use every bin boundary; counts retain their original interval widths."""
    if not len(bars.counts):
        return
    style = implot.Spec(line_color=color, fill_color=color)
    style.flags = implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded
    implot.plot_stairs(
        name,
        np.concatenate(([bars.edges[0]], bars.edges, [bars.edges[-1]])),
        np.concatenate(([0, bars.counts[0]], bars.counts, [0])),
        style,
    )


def draw_profile(
    profile: ColumnProfile,
    bars: Bars,
    height: float,
    axes: AxisControls | None = None,
    fit: bool = False,
) -> bool:
    if not len(bars.counts):
        return False
    categories = profile.kind == ProfileKind.CATEGORICAL
    if fit:
        implot.set_next_axes_to_fit()
    implot.push_style_var(implot.StyleVar_.fit_padding, imgui.ImVec2(0.1, 0.05))
    opened = implot.begin_plot(profile.name, (-1, height), implot.Flags_.no_legend)
    if not opened:
        implot.pop_style_var()
        return False
    if categories:
        implot.setup_axes("Rows", "", y_flags=implot.AxisFlags_.invert)
        implot.setup_axis_ticks(
            implot.ImAxis_.y1, bars.positions.tolist(), list(bars.labels)
        )
        if axes is not None:
            axes.apply()
        style = implot.Spec()
        style.flags = implot.BarsFlags_.horizontal
        implot.plot_bars("Rows", bars.counts, bars.positions, 0.8, style)
    else:
        xlabel = (
            f"{profile.name} / {profile.histogram_scale:.6g}"
            if profile.histogram_scale != 1
            else profile.name
        )
        implot.setup_axes(xlabel, "Rows")
        if bars.tick_labels:
            stride = max(1, (len(bars.edges) - 1 + 3) // 4)
            indices = list(range(0, len(bars.edges) - 1, stride)) + [
                len(bars.edges) - 1
            ]
            implot.setup_axis_ticks(
                implot.ImAxis_.x1,
                [float(bars.edges[i]) for i in indices],
                [bars.tick_labels[i] for i in indices],
            )
        if axes is not None:
            axes.apply()
        draw_histogram(
            "Rows",
            bars,
            profile_color(profile.name)
            if profile.kind == ProfileKind.NUMERIC
            else None,
        )
    if axes is not None:
        axes.observe()
    implot.end_plot()
    implot.pop_style_var()
    return True
