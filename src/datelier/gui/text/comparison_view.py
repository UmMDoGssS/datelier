"""Editor-level native comparisons; corpus work only starts on explicit input."""

from dataclasses import dataclass
from weakref import ReferenceType, ref

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.text.comparison_charts import (
    frequency_chart,
    frequency_table,
    length_chart,
    statistics_table,
)
from datelier.gui.text.comparison_controls import controls
from datelier.inspection.text.comparisons.settings import TextComparisonSettings
from datelier.inspection.text.comparisons.types import PreparedTextComparison


@dataclass
class TextComparisonView:
    source: int = 0
    bin: int = 0
    documents: bool = False
    last: ReferenceType[PreparedTextComparison] | None = None
    plot_frames: int = 0
    rendered_rows: int = 0
    error: str = ""

    def show(self, editor: EditorSession) -> None:
        if imgui.button("New text comparison") and len(editor.text_comparisons) < 32:
            editor.text_comparisons += (TextComparisonSettings(),)
            editor.text_comparison_index = len(editor.text_comparisons) - 1
        if not editor.text_comparisons:
            imgui.text_wrapped(
                "Map text fields from multiple files or named views "
                "and prepare their corpora with one shared tokenizer."
            )
            return
        selected = min(editor.text_comparison_index, len(editor.text_comparisons) - 1)
        _, selected = imgui.combo(
            "Text comparison",
            selected,
            [f"Text comparison {i + 1}" for i in range(len(editor.text_comparisons))],
        )
        editor.text_comparison_index = selected
        recipe = editor.text_comparisons[selected]
        if imgui.collapsing_header("Text mappings and shared tokenizer"):
            recipe = controls(editor, recipe)
            editor.text_comparisons = tuple(
                recipe if i == selected else r
                for i, r in enumerate(editor.text_comparisons)
            )
        jobs = editor.text_comparison_jobs
        jobs.bind(recipe, editor.text_comparison_inputs(recipe))
        if imgui.button("Remove text comparison"):
            editor.text_comparisons = tuple(
                r for i, r in enumerate(editor.text_comparisons) if i != selected
            )
            jobs.clear()
            self.last = None
            return
        if imgui.button("Prepare text comparison"):
            try:
                jobs.request()
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon text comparison"):
                jobs.clear()
                jobs.message = "Executing work is abandoned and cannot publish."
            phase, done, total = jobs.progress.value
            imgui.text_wrapped(f"{phase} · {done:,}/{total:,}")
        imgui.text_wrapped(self.error or jobs.message)
        result = jobs.active
        if result is None:
            self.last = None
            return
        imgui.text_wrapped(
            f"Shared {result.settings.tokens.mode} / "
            f"{result.settings.tokens.normalization} · "
            f"lowercase {result.settings.tokens.lowercase} · {result.settings.scale}"
        )
        fit = self.last is None or self.last() is not result
        if imgui.begin_tab_bar("Shared text comparison views"):
            if imgui.begin_tab_item("Lengths")[0]:
                if length_chart(result, fit):
                    self.plot_frames += 1
                self.source = min(self.source, len(result.profiles) - 1)
                _, self.source = imgui.combo(
                    "Text selection source", self.source, list(result.labels)
                )
                labels = [
                    f"[{a:.6g}, {b:.6g}{']' if i == len(result.centers) - 1 else ')'}"
                    for i, (a, b) in enumerate(
                        zip(result.edges[:-1], result.edges[1:], strict=True)
                    )
                ]
                _, self.bin = imgui.combo(
                    "Text length bin", min(self.bin, len(labels) - 1), labels
                )
                if imgui.button("Select matching text rows"):
                    editor.select_text_comparison(result, self.source, self.bin)
                imgui.text_wrapped(jobs.selection_message)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Statistics")[0]:
                statistics_table(result)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Token frequencies")[0]:
                changed, self.documents = imgui.checkbox(
                    "Document frequency", self.documents
                )
                if frequency_chart(result, self.documents, fit or changed):
                    self.plot_frames += 1
                self.rendered_rows = frequency_table(result, self.documents)
                imgui.end_tab_item()
            imgui.end_tab_bar()
        self.last = ref(result)
