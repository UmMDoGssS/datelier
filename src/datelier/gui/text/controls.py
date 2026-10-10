"""Visible text/tokenizer choices; importing and encoding are worker commands."""

from dataclasses import dataclass, replace
from pathlib import Path

from imgui_bundle import imgui

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.list_records import is_text_field, is_text_list
from datelier.inspection.text.types import Normalization, TextSource, TokenMode


@dataclass
class TextControls:
    tokenizer_path: str = ""
    columns: tuple[str, ...] = ()
    list_columns: tuple[str, ...] = ()
    import_pixel: tuple[float, float] = (0, 0)
    prepare_pixel: tuple[float, float] = (0, 0)

    def bind(
        self, jobs: TextJobs, dataset: Dataset | None, default_column: str | None = None
    ) -> None:
        self.columns = (
            tuple(
                name
                for name, dtype in dataset.table.schema.items()
                if is_text_field(dtype)
            )
            if dataset
            else ()
        )
        self.list_columns = (
            tuple(
                name
                for name, dtype in dataset.table.schema.items()
                if is_text_list(dtype)
            )
            if dataset
            else ()
        )
        if (
            jobs.settings.column in self.list_columns
            and jobs.settings.source == TextSource.EXTERNAL
        ):
            jobs.settings = replace(jobs.settings, source=TextSource.AUTO)
        if jobs.settings.column is None and self.columns and dataset is not None:
            preferred = (
                default_column
                if default_column in self.columns
                else next(
                    (
                        n
                        for n in self.columns
                        if dataset.role(n).role
                        in (
                            ColumnRole.TEXT,
                            ColumnRole.EXTERNAL_TEXT,
                            ColumnRole.LIST_TEXT,
                        )
                    ),
                    self.columns[0],
                )
            )
            jobs.settings = replace(jobs.settings, column=preferred)

    def show(self, jobs: TextJobs) -> Path | None:
        import_path = None
        settings = jobs.settings
        text_list = settings.column in self.list_columns
        sources = (
            [TextSource.AUTO, TextSource.INLINE] if text_list else list(TextSource)
        )
        selected_source = (
            settings.source if settings.source in sources else TextSource.AUTO
        )
        _, source = imgui.combo(
            "Text source", sources.index(selected_source), [s.value for s in sources]
        )
        encodings = ["utf8", "utf-8-sig", "utf16", "latin1"]
        _, encoding = imgui.combo(
            "Text encoding", encodings.index(settings.encoding), encodings
        )
        tokens = settings.tokens
        modes = list(TokenMode)
        _, mode = imgui.combo(
            "Tokenizer", modes.index(tokens.mode), [m.value for m in modes]
        )
        normalizers = list(Normalization)
        _, norm = imgui.combo(
            "Normalization",
            normalizers.index(tokens.normalization),
            [n.value for n in normalizers],
        )
        _, lowercase = imgui.checkbox("Lowercase tokens", tokens.lowercase)
        whitespace = tokens.character_whitespace
        if modes[mode] == TokenMode.CHARACTER:
            _, whitespace = imgui.checkbox("Count whitespace code points", whitespace)
        add, count = tokens.add_special_tokens, tokens.count_special_tokens
        if modes[mode] in (TokenMode.BPE, TokenMode.UNIGRAM):
            _, add = imgui.checkbox("Add configured special tokens", add)
            _, count = imgui.checkbox("Count special tokens", count)
        _, position = imgui.input_int("Text table row", settings.position + 1)
        element = settings.element_index
        if text_list:
            _, choice = imgui.input_int("Text list element (1-based)", element + 1)
            element = max(0, choice - 1)
            imgui.text_wrapped(
                "Elements are flattened in source order within this row; "
                "null/empty sublists contribute no elements."
            )
        jobs.settings = replace(
            settings,
            source=sources[source],
            encoding=encodings[encoding],
            position=max(0, position - 1),
            element_index=element,
            tokens=replace(
                tokens,
                mode=modes[mode],
                normalization=normalizers[norm],
                lowercase=lowercase,
                character_whitespace=whitespace,
                add_special_tokens=add,
                count_special_tokens=count,
            ),
        )
        units = {
            TokenMode.CHARACTER: "Unicode code points after normalization.",
            TokenMode.WHITESPACE: "Non-whitespace runs after normalization.",
            TokenMode.WORD: (
                "Unicode word runs and punctuation runs; "
                "no language-specific segmentation."
            ),
            TokenMode.BPE: (
                "Local BPE pieces; normalization precedes the imported normalizer."
            ),
            TokenMode.UNIGRAM: (
                "Local Unigram pieces; normalization precedes the imported normalizer."
            ),
        }
        imgui.text_wrapped(units[modes[mode]])
        artifact = tokens.artifact
        if artifact is not None:
            imgui.text_wrapped(f"Local {artifact.mode}: {artifact.path}")
            imgui.text_wrapped(f"Tokenizer SHA-256: {artifact.sha256}")
        if imgui.collapsing_header(
            "Load local tokenizer",
            imgui.TreeNodeFlags_.default_open
            if modes[mode] in (TokenMode.BPE, TokenMode.UNIGRAM)
            else 0,
        ):
            _, self.tokenizer_path = imgui.input_text(
                "Tokenizer JSON path", self.tokenizer_path
            )
            if imgui.button("Load tokenizer JSON"):
                import_path = Path(self.tokenizer_path)
            self.import_pixel = pixel()
        return import_path


def pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
