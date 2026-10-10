"""Explicit column comparison drafts use shared selectors and typed fields."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.columns import SingleSelection
from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.columns import ColumnComparisonController
from datelier.gui.comparisons.base import ComparisonTools
from datelier.gui.comparisons.source_controls import ContributorControls
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, IntegerField
from datelier.gui.components.native import target
from datelier.gui.profiles.colors import profile_color
from datelier.inspection.comparison_settings import ComparisonSource, Normalization


class SourceCaption(Component):
    def __init__(self, model: ColumnComparisonController, identity: str) -> None:
        super().__init__("caption")
        self.model, self.identity = model, identity

    def render(self, frame: FrameContext) -> None:
        source = self.model.catalog.by_id.get(self.identity)
        imgui.separator_text(source.title if source else self.identity)


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
                SourceCaption(model, identity),
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
                ChoiceField(
                    "recipe",
                    "Comparison",
                    lambda: tuple(range(len(model.recipes))),
                    lambda: model.index,
                    model.choose,
                    labels=lambda: tuple(
                        f"Comparison {i + 1}" for i in range(len(model.recipes))
                    ),
                ),
                CommandButton("new", "New comparison", model.new),
                CommandButton(
                    "remove",
                    "Remove comparison",
                    model.remove,
                    lambda: bool(model.recipes),
                ),
                CommandButton("apply", "Apply comparison", model.apply),
                JobFeedback(
                    "job",
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
                ChoiceField(
                    "source",
                    "Link rows in source",
                    lambda: (
                        tuple(range(len(model.active.series))) if model.active else ()
                    ),
                    lambda: model.selected_source,
                    lambda value: setattr(model, "selected_source", value),
                    labels=lambda: (
                        tuple(s.label for s in model.active.series)
                        if model.active
                        else ()
                    ),
                ),
                IntegerField(
                    "bin",
                    "Bin / category (0-based)",
                    lambda: model.selected_bin,
                    lambda value: setattr(model, "selected_bin", value),
                ),
                CommandButton(
                    "select",
                    "Select matching rows",
                    lambda: model.select(model.selected_source, model.selected_bin),
                    lambda: model.active is not None,
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
