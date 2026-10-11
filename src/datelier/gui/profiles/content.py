"""Profile content families selected by prepared presentation kind."""

from dataclasses import fields

import numpy as np
from imgui_bundle import imgui, implot

from datelier.application.exploration import ProfileController, ProfileFamily
from datelier.gui.components.axes import AxisPlot, apply_axes, observe_axes
from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.native import label_text
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.profiles.base import ProfileContent
from datelier.gui.profiles.charts import CHARTS
from datelier.gui.profiles.distribution_facts import DistributionFacts
from datelier.inspection.profiles import ProfileKind


class ProfileFacts(Component):
    def __init__(self, model: ProfileController) -> None:
        super().__init__("facts")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        data = self.model.explorer.profiles.active
        if data is None:
            return
        for profile in data.profiles.columns:
            imgui.text_wrapped(
                f"{profile.name} · {profile.counted_rows:,} counted · "
                f"{profile.null_count:,} null · {profile.nonfinite_count:,} nonfinite"
            )
            if profile.note:
                imgui.text_wrapped(profile.note)
        if data.message:
            imgui.text_wrapped(data.message)


def statistic_rows(model: ProfileController) -> tuple[tuple[object, ...], ...]:
    data = model.explorer.profiles.active
    if data is None:
        return ()
    rows: list[tuple[object, ...]] = []
    for profile in data.profiles.columns:
        statistics = profile.statistics
        if statistics is not None:
            rows.extend(
                (
                    profile.name,
                    field.name.replace("_", " "),
                    getattr(statistics, field.name),
                )
                for field in fields(statistics)
            )
        else:
            rows.extend(
                (
                    (profile.name, "Non-null", profile.nonnull_count),
                    (profile.name, "Unique", profile.unique_count),
                    (profile.name, "Minimum", profile.minimum),
                    (profile.name, "Maximum", profile.maximum),
                )
            )
        lists = profile.list_statistics
        if lists:
            rows.extend(
                (
                    (profile.name, "Elements", lists.elements),
                    (profile.name, "Null elements", lists.null_elements),
                    (profile.name, "Rectangular", lists.rectangular),
                    (profile.name, "Ragged", lists.ragged),
                )
            )
            for dimension in lists.dimensions:
                rows.extend(
                    (
                        profile.name,
                        f"Depth {dimension.depth}: {field.name}",
                        getattr(dimension, field.name),
                    )
                    for field in fields(dimension)
                )
            rows.extend(
                (profile.name, f"Shape {shape}", count) for shape, count in lists.shapes
            )
    return tuple(rows)


class ColumnProfileContent(ProfileContent):
    @property
    def family(self) -> ProfileFamily:
        return ProfileFamily.COLUMNS

    def __init__(
        self, key: str, model: ProfileController, children: tuple[Component, ...] = ()
    ) -> None:
        self.model = model
        facts = (
            ProfileFacts(model),
            FactsTable(
                "statistics",
                ("Column", "Statistic", "Value"),
                lambda: statistic_rows(model),
                160,
            ),
        )
        super().__init__(key, (*children, *facts))


class NumericContent(ColumnProfileContent):
    def __init__(self, model: ProfileController) -> None:
        self.charts = tuple(
            chart(
                lambda: (
                    model.explorer.profiles.active.comparison
                    if model.explorer.profiles.active
                    else None
                )
            )
            for chart in CHARTS
        )
        self.viewport = ResizableViewport(
            "numeric-plot",
            self.charts[0],
            height=260,
            read_height=lambda: model.height,
            write_height=lambda value: setattr(model, "height", value),
        )
        super().__init__(
            "numeric",
            model,
            (
                self.viewport,
                DistributionFacts(self.charts[0].prepared, lambda: model.mode),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        chart = self.charts[self.model.mode]
        if self.viewport.content is not chart:
            self.viewport.content = chart
            self.viewport.children = (chart,)
            chart.fit = True
        super().render(frame)


class ProfileBars(AxisPlot):
    def __init__(self, model: ProfileController) -> None:
        super().__init__("bars")
        self.model = model

    def plot_scope(self) -> object:
        return id(self.model.explorer.profiles.active)

    def numeric_axes(self) -> tuple[bool, bool]:
        data = self.model.explorer.profiles.active
        return bool(data and data.bars and len(data.bars[0].edges)), True

    def render_plot(self, frame: FrameContext) -> None:
        data = self.model.explorer.profiles.active
        if data is None or not data.bars:
            return
        bars = data.bars[0]
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##profile", (-1, max(120, self.height - 30))):
            implot.setup_axes("Value", "Count")
            if not len(bars.edges):
                implot.setup_axis_ticks(
                    implot.ImAxis_.x1, bars.positions.tolist(), list(bars.labels)
                )
            apply_axes(self.axes)
            implot.plot_bars(
                label_text(data.profiles.columns[0].name),
                bars.positions,
                bars.counts,
                float(np.diff(bars.edges)[0]) if len(bars.edges) > 1 else 0.7,
            )
            observe_axes(self.axes, frame)
            implot.end_plot()
            self.fit = False


class CountContent(ColumnProfileContent):
    def __init__(self, model: ProfileController) -> None:
        super().__init__(
            "counts",
            model,
            (
                ResizableViewport(
                    "count-plot",
                    ProfileBars(model),
                    height=240,
                    read_height=lambda: model.height,
                    write_height=lambda value: setattr(model, "height", value),
                ),
            ),
        )


class StructureContent(ColumnProfileContent):
    def __init__(self, model: ProfileController) -> None:
        super().__init__("structure", model)


class ProfileRouter(ProfileContent):
    @property
    def family(self) -> ProfileFamily:
        return ProfileFamily.COLUMNS

    def __init__(self, model: ProfileController) -> None:
        self.model = model
        numeric, counts, structure = (
            NumericContent(model),
            CountContent(model),
            StructureContent(model),
        )
        self.registry: dict[ProfileKind, ProfileContent] = {
            ProfileKind.NUMERIC: numeric,
            ProfileKind.CATEGORICAL: counts,
            ProfileKind.TEMPORAL: counts,
            ProfileKind.LIST: structure,
            ProfileKind.OBJECT: structure,
        }
        self.fallback = structure
        super().__init__("content", ())

    def render(self, frame: FrameContext) -> None:
        group = self.model.explorer.profiles.active
        if not self.model.selected:
            imgui.text("Choose a column to inspect.")
            return
        if group is None or not group.profiles.columns:
            imgui.text_wrapped(
                self.model.explorer.profiles.message or "Choose a column to inspect."
            )
            return
        self.children = (
            self.registry.get(group.profiles.columns[0].kind, self.fallback),
        )
        super().render(frame)

    def close(self) -> None:
        for content in set(self.registry.values()):
            content.close()
