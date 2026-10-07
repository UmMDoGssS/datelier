"""Saved native image comparisons; collection work requires an explicit command."""

from dataclasses import replace

import numpy as np
from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.images.comparison_charts import draw_curve
from datelier.gui.images.comparison_controls import controls
from datelier.gui.images.profile_tables import record_outcomes, statistics
from datelier.gui.plots.area import PlotArea
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonViewSettings,
)
from datelier.inspection.images.comparisons.types import (
    ImageComparisonCurve,
    PreparedImageComparison,
)


class ImageComparisonView:
    def __init__(self) -> None:
        self.area = PlotArea()
        self.plot_frames = 0
        self.rendered_rows = 0
        self._observed: ImageComparisonViewSettings | None = None
        self.error = ""

    def show(self, editor: EditorSession) -> None:
        if imgui.button("New image comparison") and len(editor.image_comparisons) < 32:
            editor.image_comparisons += (ImageComparisonSettings(),)
            editor.image_comparison_index = len(editor.image_comparisons) - 1
        if not editor.image_comparisons:
            imgui.text_wrapped(
                "Map image fields or confirmed image views across files, then "
                "explicitly prepare dimensions and colors."
            )
            return
        selected = min(editor.image_comparison_index, len(editor.image_comparisons) - 1)
        _, selected = imgui.combo(
            "Image comparison",
            selected,
            [
                f"Image comparison {index + 1}"
                for index in range(len(editor.image_comparisons))
            ],
        )
        editor.image_comparison_index = selected
        recipe = editor.image_comparisons[selected]
        if imgui.collapsing_header("Image mappings and scopes"):
            recipe = controls(editor, recipe)
            editor.image_comparisons = tuple(
                recipe if index == selected else current
                for index, current in enumerate(editor.image_comparisons)
            )
        jobs = editor.image_comparison_jobs
        jobs.bind(recipe, editor.image_comparison_inputs(recipe))
        if imgui.button("Remove image comparison"):
            editor.image_comparisons = tuple(
                current
                for index, current in enumerate(editor.image_comparisons)
                if index != selected
            )
            jobs.clear()
            return
        imgui.same_line()
        if imgui.button("Prepare image comparison"):
            try:
                jobs.request()
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon image comparison"):
                jobs.clear()
                jobs.message = "Executing work is abandoned and cannot publish."
            phase, done, total = jobs.progress.value
            imgui.text(f"{phase} · {done:,}/{total:,}")
        imgui.text_wrapped(self.error or jobs.message)
        result = jobs.active
        if result is None:
            return
        settings = editor.image_comparison_view
        requested = settings.tab if settings != self._observed else ""
        if imgui.begin_tab_bar("Image comparison views"):
            for label in ("Dimensions", "Colors", "Statistics", "Records"):
                flags = imgui.TabItemFlags_.set_selected if requested == label else 0
                if imgui.begin_tab_item(label, flags=flags)[0]:
                    settings = replace(settings, tab=label)
                    if label in ("Dimensions", "Colors"):
                        settings = self._distribution(editor, result, settings)
                    else:
                        settings = self._source(editor, result, settings)
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        editor.image_comparison_view = settings
        self._observed = settings

    def _distribution(
        self,
        editor: EditorSession,
        result: PreparedImageComparison,
        settings: ImageComparisonViewSettings,
    ) -> ImageComparisonViewSettings:
        if settings.tab == "Dimensions":
            names = ["Width", "Height", "Aspect ratio"]
            _, current = imgui.combo(
                "Compared image dimension", names.index(settings.dimension), names
            )
            settings = replace(settings, dimension=names[current])
            curve = next(
                curve
                for curve in result.curves
                if curve.key.mode == "Dimensions"
                and curve.key.name == settings.dimension
            )
        else:
            curves = tuple(
                curve for curve in result.curves if curve.key.mode != "Dimensions"
            )
            families = tuple(
                dict.fromkeys((curve.key.mode, curve.key.dtype) for curve in curves)
            )
            if not families:
                imgui.text("No decoded color families. Inspect source outcomes.")
                return settings
            selected = (settings.mode, settings.dtype)
            index = families.index(selected) if selected in families else 0
            _, index = imgui.combo(
                "Compared color family",
                index,
                [f"{mode} · {np.dtype(dtype)}" for mode, dtype in families],
            )
            mode, dtype = families[index]
            channels = tuple(
                curve
                for curve in curves
                if (curve.key.mode, curve.key.dtype) == (mode, dtype)
            )
            names = [curve.key.name for curve in channels]
            current = names.index(settings.channel) if settings.channel in names else 0
            _, current = imgui.combo("Compared color channel", current, names)
            settings = replace(settings, mode=mode, dtype=dtype, channel=names[current])
            curve = channels[current]
        _, proportion = imgui.checkbox("Compare proportions", settings.proportions)
        settings = replace(settings, proportions=proportion)
        for index, profile in enumerate(result.profiles):
            imgui.text_wrapped(
                f"{result.labels[index]} · "
                f"{profile.ready}/{profile.records.height} images · "
                f"{profile.profiled_pixels:,}/{profile.total_pixels:,} pixels · "
                f"{profile.settings.scope.mode} · {profile.settings.pixels}"
            )
            if curve.counts[index] is None:
                imgui.text("This source has no values in the chosen physical family.")
        chart = next((chart for chart in curve.counts if chart is not None), None)
        if chart is not None and chart.scaled:
            imgui.text_wrapped(
                f"Scaled coordinates 0–1 represent original "
                f"{chart.minimum}–{chart.maximum}. Statistics retain exact values."
            )
        self.area.height = settings.height
        if self.area.show(
            "Image comparison distribution",
            (id(result), curve.key, settings.proportions),
            lambda height, fit, axes: draw_curve(
                result, curve, settings.proportions, height, fit, axes
            ),
        ):
            self.plot_frames += 1
        settings = replace(settings, height=max(80, min(800, int(self.area.height))))
        if settings.tab == "Dimensions":
            settings = self._selection(editor, result, curve, settings)
        return settings

    def _selection(
        self,
        editor: EditorSession,
        result: PreparedImageComparison,
        curve: ImageComparisonCurve,
        settings: ImageComparisonViewSettings,
    ) -> ImageComparisonViewSettings:
        source = min(settings.source, len(result.profiles) - 1)
        _, source = imgui.combo("Image selection source", source, list(result.labels))
        chart = curve.counts[source]
        if chart is None:
            return replace(settings, source=source)
        labels = [
            f"Bin {index + 1}: {lo:.6g}–{hi:.6g}"
            for index, (lo, hi) in enumerate(
                zip(chart.edges[:-1], chart.edges[1:], strict=True)
            )
        ]
        _, selected = imgui.combo(
            "Image dimension bin", min(settings.bin_index, len(labels) - 1), labels
        )
        if imgui.button("Select matching image rows"):
            try:
                editor.select_image_comparison(
                    result, source, settings.dimension, selected
                )
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        imgui.text_wrapped(editor.image_comparison_jobs.selection_message)
        return replace(settings, source=source, bin_index=selected)

    def _source(
        self,
        editor: EditorSession,
        result: PreparedImageComparison,
        settings: ImageComparisonViewSettings,
    ) -> ImageComparisonViewSettings:
        source = min(settings.source, len(result.profiles) - 1)
        _, source = imgui.combo("Image result source", source, list(result.labels))
        profile = result.profiles[source]
        imgui.text(
            f"{profile.ready} ready · {profile.nulls} null · "
            f"{profile.unresolved} unresolved · {profile.failures} failed"
        )
        if settings.tab == "Statistics":
            statistics(
                "Compared image statistics",
                (*profile.dimension_summaries, *profile.summaries),
                260,
            )
        else:
            file = next(
                (
                    file
                    for file in editor.file_sessions
                    if file.identity == profile.file_id
                ),
                None,
            )
            if file is not None:
                self.rendered_rows = record_outcomes(
                    profile,
                    file,
                    lambda row: self._open_record(editor, result, source, row),
                )
        return replace(settings, source=source)

    def _open_record(
        self,
        editor: EditorSession,
        result: PreparedImageComparison,
        source: int,
        row: int,
    ) -> None:
        try:
            editor.open_image_comparison_record(result, source, row)
            self.error = ""
        except ValueError as error:
            self.error = str(error)
