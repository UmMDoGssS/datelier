"""Related category charts share prepared provenance, sizing and scoped row input."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.axes import AxisPlot, apply_axes, observe_axes
from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import label_text, target
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.profiles.colors import profile_color
from datelier.gui.profiles.primitives import box_label, draw_box
from datelier.gui.relationships.primitives import legend_hovered
from datelier.plotting.categories import CategoryChart, CategoryRepresentation
from datelier.plotting.selection import LinkedSelection


class CategoryInput(Component):
    def __init__(
        self,
        prepared: Callable[[], CategoryChart | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        hit: Callable[[CategoryChart, implot.Point], tuple[int, int] | None],
    ) -> None:
        super().__init__("input")
        self.prepared, self.selection, self.jump, self.hit = (
            prepared,
            selection,
            jump,
            hit,
        )

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        if implot.is_plot_hovered() and not legend_hovered():
            chosen = self.hit(data, implot.get_plot_mouse_pos())
            if chosen is not None:
                group, category = chosen
                count = int(data.counts[group, category])
                imgui.set_tooltip(
                    f"{data.labels[category]} · {data.groups[group]}\n"
                    f"{count:,} source rows · {data.value_label}: "
                    f"{data.values[group, category]:.6g}"
                )
                if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                    ids = data.row_ids[group][category]
                    if self.selection.choose(
                        data.revision, ids, toggle=imgui.get_io().key_ctrl
                    ):
                        self.jump(data.first_positions[group][category])
                        if len(ids) < count:
                            self.selection.message += (
                                f" First {len(ids):,} of {count:,} matching rows."
                            )
        implot.get_input_map().pan = imgui.MouseButton_.middle


class CategoryPlot(AxisPlot, ABC):
    def __init__(
        self,
        key: str,
        prepared: Callable[[], CategoryChart | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__(key)
        self.prepared = prepared
        self.selection = selection
        self._stamp: tuple[object, ...] = ()
        self.children = (CategoryInput(prepared, selection, jump, self.hit),)

    @abstractmethod
    def setup_axes(self, data: CategoryChart) -> None: ...

    @abstractmethod
    def draw(self, data: CategoryChart, frame: FrameContext) -> None: ...

    @abstractmethod
    def hit(
        self, data: CategoryChart, point: implot.Point
    ) -> tuple[int, int] | None: ...

    def plot_scope(self) -> object:
        data = self.prepared()
        return (data.revision, data.settings) if data else None

    def render_plot(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            imgui.text_wrapped(
                "Choose available category/value columns. Preparing relationships…"
            )
            return
        if not data.labels:
            imgui.text_wrapped("No finite values to plot.")
            return
        stamp = data.revision, data.settings
        if stamp != self._stamp:
            self._stamp, self.fit = stamp, True
        imgui.text_wrapped(
            f"{data.included_rows:,} included of {data.input_rows:,} prepared / "
            f"{data.total_rows:,} rows · {data.excluded_values:,} "
            f"missing/nonfinite excluded · {len(self.selection.row_ids):,} selected"
        )
        if data.other_categories or data.other_groups:
            imgui.text_wrapped(
                f"Other includes {data.other_categories:,} additional categories "
                f"and {data.other_groups:,} additional groups."
            )
        notes = tuple(dict.fromkeys(s.note for s in data.distributions if s.note))
        for note in notes[:3]:
            imgui.text_wrapped(note)
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##category", (-1, max(120, self.height - 85))):
            self.setup_axes(data)
            apply_axes(self.axes)
            implot.setup_legend(
                implot.Location_.north,
                implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
            )
            self.draw(data, frame)
            self.render_children(frame)
            observe_axes(self.axes, frame)
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False

    def close(self) -> None:
        self._stamp = ()
        super().close()


class CategoryBars(CategoryPlot):
    def __init__(
        self,
        prepared: Callable[[], CategoryChart | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("category-bars", prepared, selection, jump)

    def numeric_axes(self) -> tuple[bool, bool]:
        return True, False

    def setup_axes(self, data: CategoryChart) -> None:
        implot.setup_axes(
            data.value_label, data.settings.category, y_flags=implot.AxisFlags_.invert
        )
        implot.setup_axis_ticks(
            implot.ImAxis_.y1,
            [float(i) for i in range(len(data.labels))],
            list(data.labels),
        )

    def draw(self, data: CategoryChart, frame: FrameContext) -> None:
        positions = np.arange(len(data.labels), dtype=np.float64)
        width = 0.8 / len(data.groups)
        for group, name in enumerate(data.groups):
            ys = positions - 0.4 + width * (group + 0.5)
            implot.plot_bars(
                label_text(name) + f"##group/{group}",
                data.values[group],
                ys,
                width,
                implot.Spec(
                    flags=implot.BarsFlags_.horizontal, fill_color=profile_color(name)
                ),
            )
            for category, value in enumerate(data.values[group]):
                point = implot.plot_to_pixels(float(value) / 2, float(ys[category]))
                frame.record(f"bar-{group}-{category}", (point.x, point.y))

    def hit(self, data: CategoryChart, point: implot.Point) -> tuple[int, int] | None:
        category = int(np.floor(point.y + 0.5))
        width = 0.8 / len(data.groups)
        group = int(np.floor((point.y - category + 0.4) / width))
        if (
            0 <= category < len(data.labels)
            and 0 <= group < len(data.groups)
            and data.counts[group, category]
            and implot.internal.get_item(
                label_text(data.groups[group]) + f"##group/{group}"
            ).show
        ):
            value = data.values[group, category]
            if min(0, value) <= point.x <= max(0, value):
                return group, category
        return None


class CategoryDistribution(CategoryPlot, ABC):
    @property
    @abstractmethod
    def violin(self) -> bool: ...

    def numeric_axes(self) -> tuple[bool, bool]:
        return False, True

    def setup_axes(self, data: CategoryChart) -> None:
        implot.setup_axes(data.settings.category, data.value_label)
        implot.setup_axis_ticks(
            implot.ImAxis_.x1,
            [float(i) for i in range(len(data.labels))],
            list(data.labels),
        )

    def draw(self, data: CategoryChart, frame: FrameContext) -> None:
        for index, series in enumerate(data.distributions):
            draw_box(series, index, self.violin, profile_color(series.name))
            if series.box:
                point = implot.plot_to_pixels(float(index), series.box[2])
                frame.record(f"distribution-{index}", (point.x, point.y))

    def hit(self, data: CategoryChart, point: implot.Point) -> tuple[int, int] | None:
        category = round(point.x)
        if not 0 <= category < len(data.distributions) or abs(point.x - category) > 0.4:
            return None
        series = data.distributions[category]
        if (
            series.box is None
            or not implot.internal.get_item(box_label(series.name, category)).show
        ):
            return None
        lo, hi = (
            (float(series.kde_x[0]), float(series.kde_x[-1]))
            if self.violin and len(series.kde_x)
            else (series.box[0], series.box[-1])
        )
        lower, upper = (
            implot.plot_to_pixels(category, lo).y,
            implot.plot_to_pixels(category, hi).y,
        )
        if min(lower, upper) - 5 <= imgui.get_io().mouse_pos.y <= max(lower, upper) + 5:
            return 0, category
        return None


class CategoryBox(CategoryDistribution):
    @property
    def violin(self) -> bool:
        return False


class CategoryViolin(CategoryDistribution):
    @property
    def violin(self) -> bool:
        return True


class CategoryRouter(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], CategoryChart | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("category-chart")
        self.prepared = prepared
        self.routes: dict[CategoryRepresentation, CategoryPlot] = {
            **{
                mode: CategoryBars(prepared, selection, jump)
                for mode in (
                    CategoryRepresentation.COUNTS,
                    CategoryRepresentation.GROUPED,
                    CategoryRepresentation.MEAN,
                    CategoryRepresentation.MEDIAN,
                    CategoryRepresentation.SUM,
                )
            },
            CategoryRepresentation.BOX: CategoryBox(
                "category-box", prepared, selection, jump
            ),
            CategoryRepresentation.VIOLIN: CategoryViolin(
                "category-violin", prepared, selection, jump
            ),
        }

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        child = self.routes.get(data.settings.representation) if data else None
        if child:
            child.height, child.fit = self.height, self.fit or child.fit
            self.children = (child,)
            super().render(frame)
            self.fit = child.fit
        else:
            imgui.text_wrapped("Preparing category relationships…")

    def close(self) -> None:
        self.children = ()
        for child in self.routes.values():
            child.close()
