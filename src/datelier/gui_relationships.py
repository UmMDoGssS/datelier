"""Heatmap and bounded subplot grid with navigation and linked selection."""

from dataclasses import dataclass, field

from imgui_bundle import imgui, implot

from datelier.dataset import Dataset
from datelier.exploration import Explorer
from datelier.gui_axes import AxisControls
from datelier.gui_fields import combo
from datelier.gui_heatmap import HeatmapView
from datelier.gui_plot_area import PlotArea
from datelier.gui_plot_controls import PlotControls
from datelier.gui_profiles import draw_histogram
from datelier.gui_selection import ScatterInteraction
from datelier.gui_table import TableView
from datelier.relationships import Relationships
from datelier.selection import LinkedSelection


@dataclass
class RelationshipView:
    mode: int = 0
    area: PlotArea = field(default_factory=PlotArea)
    frames: int = 0
    heatmap: HeatmapView = field(default_factory=HeatmapView)
    interactions: dict[tuple[int, int], ScatterInteraction] = field(
        default_factory=dict
    )

    @property
    def pair_pixel(self) -> tuple[float, float]:
        return self.heatmap.pair_pixel

    def show_features(
        self, plots: PlotControls, explorer: Explorer, dataset: Dataset
    ) -> None:
        features = list(plots.relationship_features or ())
        if imgui.button(f"Features ({len(features)})##relationships"):
            imgui.open_popup("Relationship features")
        if imgui.begin_popup("Relationship features"):
            if imgui.begin_child("Relationship feature list", (260, 140)):
                for name in plots.numeric:
                    chosen = name in features
                    imgui.begin_disabled(not chosen and len(features) >= 16)
                    changed, checked = imgui.checkbox(name, chosen)
                    imgui.end_disabled()
                    if changed:
                        if checked:
                            features.append(name)
                        else:
                            features.remove(name)
                plots.relationship_features = features
            imgui.end_child()
            imgui.begin_disabled(len(features) < 2)
            if imgui.button("Apply features"):
                explorer.request(dataset, plots.settings())
                imgui.close_current_popup()
            imgui.end_disabled()
            imgui.end_popup()

    def show(
        self, data: Relationships, selection: LinkedSelection, table: TableView
    ) -> tuple[str, str | None] | None:
        choices = ["Heatmap", "Pair grid"] if 0 < len(data.names) <= 8 else ["Heatmap"]
        self.mode = min(self.mode, len(choices) - 1)
        _, self.mode = combo("Chart type", self.mode, choices)
        imgui.text_wrapped(
            f"{len(data.names)} features · "
            f"{data.sampled_rows:,} / {data.total_rows:,} rows"
        )
        if imgui.collapsing_header("Details##relationships"):
            imgui.text_wrapped(
                "Pearson correlation uses pairwise finite values. "
                "Gray cells with a dash are undefined. "
                "Click a heatmap cell to open its profile or scatter. "
                "In the pair grid, click to select a row or double-click "
                "to open its axes. Grid cells show at most 150 sampled points; "
                "diagonal histograms use all finite values."
            )
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
            (selection.revision, data.names, self.mode),
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
        cell_height = max(100, label_width + 30)
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
                    implot.setup_axes(
                        (x if i == 0 else "") if dense else x,
                        (y if j == 0 else "") if dense else y if i != j else "Rows",
                        axis_flags | (implot.AxisFlags_.opposite if dense else 0),
                        axis_flags,
                    )
                    points = data.cells[i][j]
                    if points is None:
                        bars = data.diagonals[i]
                        if len(bars.counts):
                            draw_histogram(x, bars)
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
                    if hovered and dense:
                        imgui.set_tooltip(
                            f"X: {x} · Y: {y}" if i != j else f"{x}: value / row count"
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
