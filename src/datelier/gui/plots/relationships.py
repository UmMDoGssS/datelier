"""Heatmap and bounded subplot grid with navigation and linked selection."""

from dataclasses import dataclass, field

from imgui_bundle import imgui, implot

from datelier.application.columns import ColumnChoice, MultiSelection
from datelier.core.dataset import Dataset
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.help import show_help
from datelier.gui.data.table import TableView
from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.axes import AxisControls
from datelier.gui.plots.controls import PlotControls
from datelier.gui.plots.distributions import MODES
from datelier.gui.plots.heatmap import HeatmapView
from datelier.gui.plots.pair_diagonal import (
    diagonal_axes,
    diagonal_details,
    draw_diagonal,
)
from datelier.gui.plots.selection import ScatterInteraction
from datelier.gui.widgets.fields import combo
from datelier.inspection.exploration import Explorer
from datelier.plotting.relationships import Relationships
from datelier.plotting.selection import LinkedSelection


@dataclass
class RelationshipView:
    mode: int = 0
    area: PlotArea = field(default_factory=PlotArea)
    frames: int = 0
    heatmap: HeatmapView = field(default_factory=HeatmapView)
    interactions: dict[tuple[int, int], ScatterInteraction] = field(
        default_factory=dict
    )
    diagonal_mode: int = 0
    features_picker: ColumnPicker = field(
        default_factory=lambda: ColumnPicker(
            "Correlation features", MultiSelection(limit=16)
        )
    )

    def controls(
        self,
        count: int,
        plots: PlotControls | None = None,
        explorer: Explorer | None = None,
        dataset: Dataset | None = None,
    ) -> None:
        choices = ["Heatmap", "Pair grid"] if 0 < count <= 8 else ["Heatmap"]
        self.mode = min(self.mode, len(choices) - 1)
        if imgui.begin_table(
            "Correlation charts", 2, imgui.TableFlags_.sizing_stretch_same
        ):
            imgui.table_next_row()
            imgui.table_set_column_index(0)
            _, self.mode = combo("Chart type", self.mode, choices)
            if self.mode == 1:
                imgui.table_set_column_index(1)
                if plots is not None:
                    self.diagonal_mode = plots.diagonal_mode
                changed, self.diagonal_mode = combo(
                    "Diagonal", self.diagonal_mode, MODES
                )
                if (
                    changed
                    and plots is not None
                    and explorer is not None
                    and dataset is not None
                ):
                    plots.diagonal_mode = self.diagonal_mode
                    explorer.request(dataset, plots.settings())
            imgui.end_table()

    @property
    def pair_pixel(self) -> tuple[float, float]:
        return self.heatmap.pair_pixel

    def show_features(
        self, plots: PlotControls, explorer: Explorer, dataset: Dataset
    ) -> None:
        before = tuple(plots.relationship_features or ())
        features = self.features_picker.show(
            tuple(ColumnChoice(n, "Numeric", numeric=True) for n in plots.numeric),
            before,
            caption=f"Features ({len(before)})",
        )
        if features != before:
            plots.relationship_features = list(features)
            if len(features) >= 2:
                explorer.request(dataset, plots.settings())

    def show(
        self,
        data: Relationships,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None = None,
        explorer: Explorer | None = None,
        dataset: Dataset | None = None,
        *,
        controls: bool = True,
    ) -> tuple[str, str | None] | None:
        if controls:
            self.controls(len(data.names), plots, explorer, dataset)
        imgui.text_wrapped(
            f"{len(data.names)} features · "
            f"{data.sampled_rows:,} / {data.total_rows:,} rows"
        )
        imgui.text_wrapped(
            "Pearson uses pairwise finite values; gray dashes are "
            "undefined. Grid cells: up to 150 sampled points; "
            "histogram/box: all finite values; KDE/ECDF/violin: up to "
            "2,000 finite values per feature."
        )
        show_help(
            "Click a heatmap cell to open its profile or scatter. In the "
            "grid, click selects a row; double-click opens its axes."
        )
        if self.mode == 1 and data.diagonal_mode != self.diagonal_mode:
            imgui.text("Preparing diagonal distributions…")
            return None
        if not data.names:
            imgui.text("Choose numeric features to compare.")
            return None
        action = None

        def draw(height: float, fit: bool, _axes: AxisControls) -> bool:
            nonlocal action
            before = self.frames
            if self.mode == 0:
                before_heatmap = self.heatmap.frames
                action = self.heatmap.show(data, height, self.area.axes)
                self.frames += self.heatmap.frames - before_heatmap
            else:
                action = self._grid(data, selection, table, height, fit)
            return self.frames > before

        self.area.show(
            "Relationship plot",
            (selection.revision, data.names, self.mode, self.diagonal_mode),
            draw,
            numeric_axes=(False, False),
            minimum_height=170
            if self.mode
            else max(170, len(data.names) * (imgui.get_text_line_height() + 8) + 85),
        )
        return action

    def _grid(
        self,
        data: Relationships,
        selection: LinkedSelection,
        table: TableView,
        height: float,
        fit: bool,
    ) -> tuple[str, str | None] | None:
        n = len(data.names)
        if n > 8:
            imgui.text_wrapped(
                "Select at most eight relationship features for the grid."
            )
            return None
        label_width = max(imgui.calc_text_size(name).x for name in data.names)
        cell_width = max(120, label_width + 40)
        cell_height = max(100 if n > 4 else 160, label_width + 30)
        minimum_width = n * cell_width
        available = imgui.get_content_region_avail().x
        scroll = minimum_width > available
        content_height = max(
            n * cell_height,
            height - 16 - (imgui.get_style().scrollbar_size if scroll else 0),
        )
        imgui.set_next_window_content_size(
            (minimum_width if scroll else 0, content_height)
        )
        # BeginChild's window name changes under Expand. Preserve the plot IDs
        # through that child scope so zoom and linked interactions stay put.
        plot_id = imgui.get_id("Pair grid canvas")
        action = None
        shown = imgui.begin_child(
            "Pair grid canvas",
            (-1, height),
            window_flags=imgui.WindowFlags_.horizontal_scrollbar,
        )
        if shown:
            imgui.internal.push_override_id(plot_id)
            action = self._grid_cells(
                data,
                selection,
                table,
                content_height,
                fit,
            )
            imgui.pop_id()
        imgui.end_child()
        return action

    def _grid_cells(
        self,
        data: Relationships,
        selection: LinkedSelection,
        table: TableView,
        height: float,
        fit: bool,
    ) -> tuple[str, str | None] | None:
        n = len(data.names)
        action = None
        dense = n > 4
        if implot.begin_subplots("Pair grid", n, n, (-1, height)):
            for i, y in enumerate(data.names):
                for j, x in enumerate(data.names):
                    if fit:
                        implot.set_next_axes_to_fit()
                    if not implot.begin_plot(
                        f"{y} / {x}##{i}-{j}",
                        flags=implot.Flags_.no_legend
                        | (implot.Flags_.no_title if dense else 0),
                    ):
                        continue
                    axis_flags = implot.AxisFlags_.no_tick_labels if dense else 0
                    diagonal = i == j
                    xlabel, ylabel = (
                        diagonal_axes(x, data.diagonal_mode) if diagonal else (x, y)
                    )
                    implot.setup_axes(
                        (x if i == 0 else "") if dense else xlabel,
                        (y if j == 0 else "") if dense else ylabel,
                        axis_flags | (implot.AxisFlags_.opposite if dense else 0),
                        axis_flags,
                    )
                    points = data.cells[i][j]
                    if points is None:
                        if data.diagonal_mode in (3, 4):
                            implot.setup_axis_ticks(implot.ImAxis_.x1, [0.0], [x])
                        draw_diagonal(data, i)
                    else:
                        style = implot.Spec()
                        style.marker = implot.Marker_.square
                        style.marker_size = 1
                        style.line_weight = 0
                        xs, ys = selection.unselected(points)
                        implot.plot_scatter("Rows", xs, ys, style)
                        interaction = self.interactions.setdefault(
                            (i, j), ScatterInteraction()
                        )
                        interaction.show(points, selection, table)
                    hovered = implot.is_plot_hovered()
                    if hovered and (dense or diagonal):
                        imgui.set_tooltip(
                            diagonal_details(data, i)
                            if diagonal
                            else f"X: {x} · Y: {y}"
                        )
                    if hovered and (
                        imgui.is_mouse_double_clicked(imgui.MouseButton_.left)
                        or i == j
                        and imgui.is_mouse_clicked(imgui.MouseButton_.left)
                    ):
                        action = (x, y if i != j else None)
                    implot.end_plot()
            implot.end_subplots()
            self.frames += 1
        return action
