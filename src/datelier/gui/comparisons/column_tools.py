"""Explicit column comparison drafts use shared selectors and typed fields."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.comparisons import ComparisonFamily
from datelier.application.comparisons.columns import ColumnComparisonController
from datelier.application.tabular import SingleSelection
from datelier.gui.comparisons.base import ComparisonTools
from datelier.gui.comparisons.recipe_controls import (
    RecipeControls,
    RowLinkControls,
    SourceCaption,
)
from datelier.gui.comparisons.source_controls import ContributorControls
from datelier.gui.components.actions import JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.native import target
from datelier.gui.profiles.colors import profile_color
from datelier.inspection.comparison_settings import ComparisonSource, Normalization


class SourceColor(Component):
    def __init__(self, fields: StateFields[ComparisonSource]) -> None:
        super().__init__("color")
        self.fields = fields

    def render(self, frame: FrameContext) -> None:
        source = self.fields.read()
        default = profile_color(source.file_id)
        changed, value = imgui.color_edit4(
            "Color", source.color or (default.x, default.y, default.z, default.w)
        )
        target(frame, "value")
        if changed:
            self.fields.write(
                replace(source, color=(value[0], value[1], value[2], value[3]))
            )


class ColumnSourceForm(Container):
    def __init__(self, model: ColumnComparisonController, identity: str) -> None:
        self.identity = identity
        fields = StateFields(
            lambda: model.mapping(identity) or ComparisonSource(identity, ""),
            model.update_mapping,
        )
        super().__init__(
            identity,
            (
                SourceCaption(model.catalog, identity),
                ColumnPicker(
                    "column",
                    "Mapped column",
                    lambda: model.catalog.column_choices(identity),
                    lambda: (fields.read().column,),
                    lambda names: fields.write(
                        replace(
                            fields.read(),
                            column=next(iter(names), fields.read().column),
                        )
                    ),
                    SingleSelection(),
                ),
                fields.text(
                    "label",
                    "Legend label",
                    lambda s: s.label,
                    lambda s, v: replace(s, label=v),
                ),
                SourceColor(fields),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.identity)
        super().render(frame)
        imgui.pop_id()


class ColumnComparisonTools(ComparisonTools):
    def __init__(self, model: ColumnComparisonController) -> None:
        self.model = model
        fields = StateFields(
            lambda: model.draft, lambda value: setattr(model, "draft", value)
        )
        super().__init__(
            "column-comparison-tools",
            (
                RecipeControls(
                    model,
                    "Apply comparison",
                    model.apply,
                    lambda: JobSnapshot(
                        model.message, model.jobs.busy, model.jobs.selection_message
                    ),
                ),
                ContributorControls(
                    model.catalog,
                    lambda: tuple(s.file_id for s in model.draft.sources),
                    model.map_files,
                    lambda source: ColumnSourceForm(model, source.identity),
                ),
                fields.integer(
                    "bins",
                    "Common histogram bins",
                    lambda s: s.bins,
                    lambda s, v: replace(s, bins=v),
                    1,
                    100,
                ),
                fields.integer(
                    "categories",
                    "Top categories",
                    lambda s: s.category_limit,
                    lambda s, v: replace(s, category_limit=v),
                    1,
                    100,
                ),
                fields.choice(
                    "normalization",
                    "Scale",
                    tuple(Normalization),
                    lambda s: s.normalization,
                    lambda s, v: replace(s, normalization=v),
                ),
                RowLinkControls(
                    lambda: (
                        tuple(s.label for s in model.active.series)
                        if model.active
                        else ()
                    ),
                    lambda: model.selected_source,
                    lambda v: setattr(model, "selected_source", v),
                    lambda: model.selected_bin,
                    lambda v: setattr(model, "selected_bin", v),
                    lambda: model.select(model.selected_source, model.selected_bin),
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.COLUMNS

    def render(self, frame: FrameContext) -> None:
        if self.model.changed:
            imgui.text_wrapped("Unapplied comparison changes")
        super().render(frame)
