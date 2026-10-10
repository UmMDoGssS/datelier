"""Dockable editor-level comparison view; all table work is delegated to jobs."""

from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui.comparisons.charts import draw_chart
from datelier.gui.comparisons.controls import ComparisonControls
from datelier.gui.comparisons.statistics import show_statistics
from datelier.gui.editor_session import EditorSession
from datelier.gui.plots.area import PlotArea
from datelier.gui.widgets.fields import combo
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.inspection.comparisons.types import PreparedComparison


@dataclass
class ComparisonView:
    area: PlotArea = field(default_factory=PlotArea)
    controls: ComparisonControls = field(default_factory=ComparisonControls)
    selected: int = 0
    selection_source: int = 0
    selection_bin: int = 0
    select_pixel: tuple[float, float] = (0, 0)
    settings_pixel: tuple[float, float] = (0, 0)
    plot_frames: int = 0
    last_result: PreparedComparison | None = None
    error: str = ""

    def show(self, editor: EditorSession) -> None:
        if imgui.button("New comparison") and len(editor.comparisons) < 32:
            editor.comparisons += (ComparisonSettings(),)
            self.selected = len(editor.comparisons) - 1
        if not editor.comparisons:
            imgui.text_wrapped(
                "Compare columns across open files. Add a comparison, "
                "then map each source explicitly."
            )
            return
        self.selected = min(self.selected, len(editor.comparisons) - 1)
        _, self.selected = combo(
            "Comparison",
            self.selected,
            [f"Comparison {i + 1}" for i in range(len(editor.comparisons))],
        )
        recipe = editor.comparisons[self.selected]
        self.controls.bind(recipe)
        show_controls = imgui.collapsing_header("Mappings and scales")
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.settings_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if show_controls and self.controls.show(editor):
            try:
                self.controls.draft.validate()
                editor.comparisons = tuple(
                    self.controls.draft if i == self.selected else s
                    for i, s in enumerate(editor.comparisons)
                )
                editor.comparison_jobs.retry(self.controls.draft)
                self.error = ""
                return
            except ValueError as error:
                self.error = str(error)
        if imgui.button("Remove comparison"):
            editor.comparisons = tuple(
                s for i, s in enumerate(editor.comparisons) if i != self.selected
            )
            self.last_result = None
            return
        if self.error:
            imgui.text_wrapped(self.error)
        if (
            self.selected >= len(editor.comparison_jobs.states)
            or editor.comparisons[self.selected] != recipe
        ):
            return
        state = editor.comparison_jobs.states[self.selected]
        if state.result is None:
            imgui.text_wrapped(state.message)
            return
        result = state.result
        if result.settings != recipe:
            return
        fit = self.last_result is not result
        if fit:
            self.selection_bin = 0
        self.selection_source = min(self.selection_source, len(result.series) - 1)
        imgui.separator_text("Distribution")
        _, self.selection_source = combo(
            "Selection source",
            self.selection_source,
            [f"{s.label} / {s.origin.column}" for s in result.series],
        )
        bin_index: int | None = None

        def draw(height: float, fit_axes: bool, _axes: object) -> bool:
            nonlocal bin_index
            shown, bin_index = draw_chart(
                result, self.selection_source, fit or fit_axes, height
            )
            return shown

        shown = self.area.show(
            "File profiles",
            id(result),
            draw,
            numeric_axes=(True, result.kind == ColumnRole.NUMERIC),
            footer_height=150,
        )
        if shown:
            self.last_result = result
            self.plot_frames += 1
        bins = (
            [
                f"{lo:.6g} to {hi:.6g}"
                for lo, hi in zip(result.edges[:-1], result.edges[1:], strict=True)
            ]
            if result.kind == ColumnRole.NUMERIC
            else list(result.labels)
        )
        if bins:
            _, self.selection_bin = combo(
                "Bin / category", min(self.selection_bin, len(bins) - 1), bins
            )
            if imgui.button("Select matching source rows"):
                bin_index = self.selection_bin
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            self.select_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if bin_index is not None:
            try:
                editor.select_comparison(result, self.selection_source, bin_index)
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if editor.comparison_jobs.selection_message:
            imgui.text_wrapped(editor.comparison_jobs.selection_message)
        imgui.text_wrapped(result.note)
        show_statistics(result)
