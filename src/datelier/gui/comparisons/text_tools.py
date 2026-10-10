"""Text sources compose common contributor, tokenizer, scope and recipe controls."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.columns import SingleSelection
from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.text import TextComparisonController
from datelier.gui.comparisons.base import ComparisonTools
from datelier.gui.comparisons.recipe_controls import (
    RecipeControls,
    RowLinkControls,
    SourceCaption,
)
from datelier.gui.comparisons.source_controls import ContributorControls
from datelier.gui.components.actions import CommandButton, JobSnapshot
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.context.text_scope import TextScopeFields
from datelier.gui.context.tokenization import TokenizationFields
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSource,
    TextScale,
)
from datelier.inspection.text.types import TextSource


class TextSourceForm(Container):
    def __init__(self, model: TextComparisonController, identity: str) -> None:
        self.identity = identity
        fields = StateFields(
            lambda: model.mapping(identity) or TextComparisonSource(identity, ""),
            model.update_mapping,
        )
        super().__init__(
            identity,
            (
                SourceCaption(model.catalog, identity),
                ColumnPicker(
                    "column",
                    "Mapped text column",
                    lambda: model.catalog.text_choices(identity),
                    lambda: (fields.read().column,),
                    lambda names: fields.write(
                        replace(
                            fields.read(),
                            column=next(iter(names), fields.read().column),
                        )
                    ),
                    SingleSelection(),
                ),
                fields.choice(
                    "source",
                    "Text source",
                    tuple(TextSource),
                    lambda s: s.source,
                    lambda s, v: replace(s, source=v),
                ),
                fields.choice(
                    "encoding",
                    "Encoding",
                    ("utf8", "utf-8-sig", "utf16", "latin1"),
                    lambda s: s.encoding,
                    lambda s, v: replace(s, encoding=v),
                ),
                TextScopeFields(
                    lambda: fields.read().scope,
                    lambda scope: fields.write(replace(fields.read(), scope=scope)),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.identity)
        super().render(frame)
        imgui.pop_id()


class TextComparisonTools(ComparisonTools):
    def __init__(self, model: TextComparisonController) -> None:
        self.model = model
        fields = StateFields(lambda: model.draft, lambda s: setattr(model, "draft", s))
        view = StateFields(lambda: model.view, lambda s: setattr(model, "view", s))
        super().__init__(
            "text-comparison-tools",
            (
                RecipeControls(
                    model,
                    "Prepare text comparison",
                    model.prepare,
                    lambda: JobSnapshot(
                        model.message, model.jobs.busy, model.jobs.selection_message
                    ),
                    model.jobs.clear,
                ),
                ContributorControls(
                    model.catalog,
                    lambda: tuple(s.file_id for s in model.draft.sources),
                    model.map_files,
                    lambda source: TextSourceForm(model, source.identity),
                ),
                CommandButton(
                    "copy-tokenizer", "Use active view tokenizer", model.copy_tokenizer
                ),
                TokenizationFields(
                    lambda: fields.read().tokens,
                    lambda tokens: fields.write(replace(fields.read(), tokens=tokens)),
                ),
                fields.integer(
                    "bins",
                    "Common length bins",
                    lambda s: s.bins,
                    lambda s, v: replace(s, bins=v),
                    1,
                    200,
                ),
                fields.choice(
                    "scale",
                    "Scale",
                    tuple(TextScale),
                    lambda s: s.scale,
                    lambda s, v: replace(s, scale=v),
                ),
                view.boolean(
                    "documents",
                    "Plot document frequencies",
                    lambda s: s.documents,
                    lambda s, v: replace(s, documents=v),
                ),
                RowLinkControls(
                    lambda: model.active.labels if model.active else (),
                    lambda: model.view.source,
                    lambda v: view.write(replace(view.read(), source=v)),
                    lambda: model.view.bin_index,
                    lambda v: view.write(replace(view.read(), bin_index=v)),
                    lambda: model.select(model.view.source, model.view.bin_index),
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.TEXT

    def render(self, frame: FrameContext) -> None:
        if self.model.changed:
            imgui.text_wrapped("Unprepared text comparison changes")
        tokens = self.model.draft.tokens
        if tokens.artifact:
            imgui.text_wrapped(
                f"Tokenizer: {tokens.artifact.path}\nSHA-256: {tokens.artifact.sha256}"
            )
        super().render(frame)
