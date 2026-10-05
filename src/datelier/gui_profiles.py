"""Render prepared profiles in value space or with explicit category names."""

from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot

from datelier.dataset import Dataset
from datelier.distributions import DistributionSettings
from datelier.exploration import Dashboard, Explorer
from datelier.gui_axes import AxisControls
from datelier.gui_distributions import MODES, show_comparison
from datelier.gui_plot_area import PlotArea
from datelier.plotting import Bars
from datelier.profiling import COUNT_ROW_LIMIT, ColumnProfile, ProfileKind


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

    def show(
        self, explorer: Explorer, dashboard: Dashboard, dataset: Dataset | None
    ) -> bool:
        profiles = dashboard.profiles
        if not profiles.columns:
            imgui.text_wrapped(
                "No analyzable columns. Change a column's role in Schema to include it."
            )
            return False
        names = [p.name for p in profiles.columns]
        self.index = min(self.index, len(names) - 1)
        if imgui.begin_table(
            "Profile controls", 2, imgui.TableFlags_.sizing_stretch_prop
        ):
            imgui.table_setup_column("Column", init_width_or_weight=0.65)
            imgui.table_setup_column("Chart type", init_width_or_weight=0.35)
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            imgui.text("Column")
            imgui.set_next_item_width(-1)
            _, self.index = imgui.combo("##Profile column", self.index, names)
            imgui.table_set_column_index(1)
            imgui.text("Chart type")
            imgui.set_next_item_width(-1)
            kind = profiles.columns[self.index].kind
            if kind == ProfileKind.NUMERIC:
                _, self.mode = imgui.combo("##Chart type", self.mode, MODES)
            else:
                imgui.combo(
                    "##Chart type",
                    0,
                    [
                        "Counts"
                        if kind == ProfileKind.CATEGORICAL
                        else "Excluded"
                        if kind in (ProfileKind.TEXT, ProfileKind.IDENTIFIER)
                        else "Histogram"
                    ],
                )
            imgui.end_table()
        profile = profiles.columns[self.index]
        imgui.text_wrapped(profile_summary(profile, profiles.row_count))
        key = (dashboard.revision, profile.name, self.mode, dashboard.settings)
        shown = False
        if not profile.counted_rows:
            imgui.text_wrapped(
                profile.note
                if profile.kind in (ProfileKind.TEXT, ProfileKind.IDENTIFIER)
                else "No values to plot."
                if not profiles.row_count
                else "No valid values to plot."
            )
        elif (
            profile.kind == ProfileKind.NUMERIC
            and self.mode > 0
            and dataset is not None
        ):
            settings = dashboard.settings.comparison
            explorer.distribution.ensure(
                dataset,
                DistributionSettings(
                    (profile.name,), bandwidth=settings.bandwidth, seed=settings.seed
                ),
                dashboard.settings.bins,
            )
            if explorer.distribution.active is not None:
                prepared = explorer.distribution.active
                shown = self.area.show(
                    "Profile plot",
                    key,
                    lambda height, fit, axes: show_comparison(
                        prepared,
                        self.mode,
                        fit,
                        title=profile.name,
                        details=False,
                        height=height,
                        axes=axes,
                    ),
                    numeric_axes=(False, True) if self.mode in (3, 4) else (True, True),
                )
            else:
                imgui.text_wrapped(explorer.distribution.message)
        else:
            shown = self.area.show(
                "Profile plot",
                key,
                lambda height, fit, axes: draw_profile(
                    profile,
                    dashboard.bars[self.index],
                    height,
                    axes,
                    fit,
                ),
                numeric_axes=(True, False)
                if profile.kind == ProfileKind.CATEGORICAL
                else (False, True)
                if profile.kind == ProfileKind.TEMPORAL
                else (True, True),
            )
        if imgui.collapsing_header("Details##profile"):
            imgui.text(f"{profile.kind} · {profile.dtype}")
            if profile.minimum:
                imgui.text_wrapped(f"Range: {profile.minimum} to {profile.maximum}")
            if profile.mean is not None:
                imgui.text(f"Mean: {profile.mean:.6g}")
            if profile.distinct_count is not None:
                imgui.text(f"Distinct counted values: {profile.distinct_count:,}")
            imgui.text_wrapped(profile.note)
            if self.mode > 0 and profile.kind == ProfileKind.NUMERIC:
                settings = dashboard.settings.comparison
                imgui.text(
                    f"KDE bandwidth {settings.bandwidth:g} · seed {settings.seed}"
                )
                prepared = explorer.distribution.active
                if prepared is not None and prepared.series[0].name == profile.name:
                    series = prepared.series[0]
                    imgui.text(
                        f"{series.sample_count:,} values for curves; "
                        f"{len(series.outliers):,} outlier points shown."
                    )
            for label, count in zip(
                dashboard.bars[self.index].labels,
                dashboard.bars[self.index].counts,
                strict=True,
            ):
                imgui.text_wrapped(f"{label}: {int(count):,}")
        return shown


def draw_histogram(name: str, bars: Bars) -> None:
    """Use every bin boundary; counts retain their original interval widths."""
    if not len(bars.counts):
        return
    style = implot.Spec()
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
        draw_histogram("Rows", bars)
    if axes is not None:
        axes.observe()
    implot.end_plot()
    implot.pop_style_var()
    return True
