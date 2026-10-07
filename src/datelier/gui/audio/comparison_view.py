"""Saved cross-file audio statistics with explicit commands and source-owned links."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.audio.comparison_charts import draw_curve
from datelier.gui.audio.comparison_controls import controls
from datelier.gui.audio.comparison_tables import (
    CHANNEL_LABELS,
    CHANNEL_NAMES,
    RECORD_LABELS,
    RECORD_NAMES,
    scalar_table,
    statistics,
)
from datelier.gui.editor_session import EditorSession
from datelier.gui.plots.area import PlotArea
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.comparisons.types import PreparedAudioComparison


class AudioComparisonView:
    def __init__(self) -> None:
        self.area = PlotArea()
        self.plot_frames = self.rendered_rows = 0
        self._observed: AudioComparisonViewSettings | None = None
        self.error = ""

    def show(self, editor: EditorSession) -> None:
        if imgui.button("New audio comparison") and len(editor.audio_comparisons) < 32:
            editor.audio_comparisons += (AudioComparisonSettings(),)
            editor.audio_comparison_index = len(editor.audio_comparisons) - 1
        if not editor.audio_comparisons:
            imgui.text_wrapped(
                "Map audio fields or confirmed waveform views across files, then "
                "explicitly prepare headers or exact signal statistics."
            )
            return
        selected = min(editor.audio_comparison_index, len(editor.audio_comparisons) - 1)
        _, selected = imgui.combo(
            "Audio comparison",
            selected,
            [f"Audio comparison {i + 1}" for i in range(len(editor.audio_comparisons))],
        )
        editor.audio_comparison_index = selected
        recipe = editor.audio_comparisons[selected]
        if imgui.collapsing_header("Audio mappings and scopes"):
            recipe = controls(editor, recipe)
            editor.audio_comparisons = tuple(
                recipe if i == selected else r
                for i, r in enumerate(editor.audio_comparisons)
            )
        jobs = editor.audio_comparison_jobs
        jobs.bind(recipe, editor.audio_comparison_inputs(recipe))
        if imgui.button("Remove audio comparison"):
            editor.audio_comparisons = tuple(
                r for i, r in enumerate(editor.audio_comparisons) if i != selected
            )
            jobs.clear()
            return
        imgui.same_line()
        if imgui.button("Prepare audio comparison"):
            try:
                jobs.request()
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon audio comparison"):
                jobs.clear()
                jobs.message = "Executing work is abandoned and cannot publish."
            phase, done, total = jobs.progress.value
            imgui.text(f"{phase} · {done:,}/{total:,}")
        imgui.text_wrapped(self.error or jobs.message)
        result = jobs.active
        if result is None:
            return
        for label, profile in zip(result.labels, result.profiles, strict=True):
            imgui.text_wrapped(
                f"{label} · {profile.ready}/{profile.records.height} ready of "
                f"{profile.available_records} current rows · {profile.nulls} null / "
                f"{profile.failures} failed · {profile.settings.scope.mode} · "
                f"{profile.settings.mode}"
            )
        settings = editor.audio_comparison_view
        requested = settings.tab if settings != self._observed else ""
        if imgui.begin_tab_bar("Audio comparison views"):
            for label in ("Distributions", "Statistics", "Records"):
                flags = imgui.TabItemFlags_.set_selected if requested == label else 0
                if imgui.begin_tab_item(label, flags=flags)[0]:
                    settings = replace(settings, tab=label)
                    settings = (
                        self._distribution(editor, result, settings)
                        if label == "Distributions"
                        else self._source(editor, result, settings)
                    )
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        editor.audio_comparison_view = settings
        self._observed = settings

    def _distribution(
        self,
        editor: EditorSession,
        result: PreparedAudioComparison,
        settings: AudioComparisonViewSettings,
    ) -> AudioComparisonViewSettings:
        saved = settings.metric, settings.family, settings.channel
        current = next(
            (
                i
                for i, c in enumerate(result.curves)
                if (c.metric.name, c.metric.family, c.metric.channel) == saved
            ),
            0,
        )
        _, current = imgui.combo(
            "Compared audio metric", current, [c.metric.label for c in result.curves]
        )
        curve = result.curves[current]
        _, proportions = imgui.checkbox(
            "Compare audio proportions", settings.proportions
        )
        settings = replace(
            settings,
            metric=curve.metric.name,
            family=curve.metric.family,
            channel=curve.metric.channel,
            proportions=proportions,
        )
        if curve.scaled:
            imgui.text_wrapped(
                f"Scaled coordinates 0–1 represent original "
                f"{curve.minimum}–{curve.maximum}. "
                "Original extrema remain in Statistics."
            )
        if curve.metric.field in (
            "clipped_fraction",
            "silent_fraction",
            "silence_fraction",
        ):
            imgui.text_wrapped(
                "Fractions use each source's saved clipping/silence thresholds. "
                "See Statistics for original rails and amplitude units."
            )
        self.area.height = settings.height
        if self.area.show(
            "Audio comparison distribution",
            (id(result), curve.metric, proportions),
            lambda height, fit, axes: draw_curve(
                result, curve, proportions, height, fit, axes
            ),
        ):
            self.plot_frames += 1
        settings = replace(settings, height=max(80, min(800, int(self.area.height))))
        statistics(result, curve)
        source = min(settings.source, len(result.profiles) - 1)
        _, source = imgui.combo("Audio selection source", source, list(result.labels))
        labels = [
            f"Bin {i + 1}: {lo:.6g}–{hi:.6g}"
            for i, (lo, hi) in enumerate(
                zip(curve.edges[:-1], curve.edges[1:], strict=True)
            )
        ]
        _, selected = imgui.combo(
            "Audio metric bin", min(settings.bin_index, len(labels) - 1), labels
        )
        if imgui.button("Select matching audio rows"):
            try:
                editor.select_audio_comparison(result, source, curve.metric, selected)
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        imgui.text_wrapped(
            jobs_message := editor.audio_comparison_jobs.selection_message
        )
        if not jobs_message:
            imgui.text_wrapped(
                "Selections and record links remain in their originating file/view."
            )
        return replace(settings, source=source, bin_index=selected)

    def _source(
        self,
        editor: EditorSession,
        result: PreparedAudioComparison,
        settings: AudioComparisonViewSettings,
    ) -> AudioComparisonViewSettings:
        source = min(settings.source, len(result.profiles) - 1)
        _, source = imgui.combo("Audio result source", source, list(result.labels))
        profile = result.profiles[source]
        if settings.tab == "Statistics":
            if not profile.channel_records.height:
                imgui.text_wrapped(
                    "Prepare exact signal statistics to inspect original channel "
                    "amplitudes and threshold-dependent fractions."
                )
            self.rendered_rows = scalar_table(
                "Compared audio channel statistics",
                profile.channel_records,
                CHANNEL_NAMES,
                CHANNEL_LABELS,
            )
        else:
            file = next(
                (f for f in editor.file_sessions if f.identity == profile.file_id), None
            )
            if file is not None:
                self.rendered_rows = scalar_table(
                    "Compared audio record outcomes",
                    profile.records,
                    RECORD_NAMES,
                    RECORD_LABELS,
                    file.selection.row_ids,
                    lambda row: self._open_record(editor, result, source, row),
                )
        return replace(settings, source=source)

    def _open_record(
        self,
        editor: EditorSession,
        result: PreparedAudioComparison,
        source: int,
        row: int,
    ) -> None:
        try:
            editor.open_audio_comparison_record(result, source, row)
            self.error = ""
        except ValueError as error:
            self.error = str(error)
