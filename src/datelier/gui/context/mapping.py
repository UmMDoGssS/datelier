"""Record layouts and scalar supporting forms borrow metadata-only controllers."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.sources.mapping import RecordMappingDraft, SupportingDraft
from datelier.application.sources.numeric import NumericSourceController
from datelier.application.tabular import SingleSelection
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, TextField
from datelier.gui.components.groups import Conditional
from datelier.gui.components.native import target
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping


class SupportingForm(Container):
    def __init__(self, draft: SupportingDraft, model: RecordMappingDraft) -> None:
        self.draft = draft
        super().__init__(
            draft.key,
            (
                TextField(
                    "column",
                    "Column name",
                    lambda: draft.column,
                    lambda value: setattr(draft, "column", value),
                ),
                ChoiceField(
                    "axis",
                    "Supporting record axis",
                    tuple(range(len(draft.shape))),
                    lambda: draft.record_axis,
                    lambda value: setattr(draft, "record_axis", value),
                ),
                TextField(
                    "fixed",
                    "Fixed supporting coordinates",
                    lambda: draft.fixed,
                    lambda value: setattr(draft, "fixed", value),
                ),
                Conditional(
                    "structured",
                    lambda: bool(draft.fields),
                    (
                        ChoiceField(
                            "field",
                            "Scalar field",
                            ("Raw scalar", *draft.fields),
                            lambda: draft.field or "Raw scalar",
                            lambda value: setattr(
                                draft, "field", None if value == "Raw scalar" else value
                            ),
                        ),
                    ),
                ),
                CommandButton(
                    "remove",
                    "Remove supporting column",
                    lambda: model.remove(draft.key),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        imgui.separator()
        imgui.text_wrapped(f"{self.draft.member} · {self.draft.shape}")
        super().render(frame)
        imgui.pop_id()


class SupportingForms(Container):
    def __init__(self, model: RecordMappingDraft) -> None:
        super().__init__("supporting", ())
        self.model = model
        self.forms: dict[str, SupportingForm] = {}

    def render(self, frame: FrameContext) -> None:
        for key in tuple(self.forms):
            if key not in {draft.key for draft in self.model.supports}:
                self.forms.pop(key).close()
        for draft in self.model.supports[
            self.model.page * 8 : (self.model.page + 1) * 8
        ]:
            if draft.key not in self.forms:
                self.forms[draft.key] = SupportingForm(draft, self.model)
        self.children = tuple(
            self.forms[draft.key]
            for draft in self.model.supports[
                self.model.page * 8 : (self.model.page + 1) * 8
            ]
        )
        super().render(frame)


class MappingForm(Container):
    def __init__(
        self,
        model: RecordMappingDraft,
        open_records: Callable[[ArrayRecordMapping], object],
    ) -> None:
        self.model = model
        super().__init__(
            "form",
            (
                ChoiceField(
                    "record-axis",
                    "Record axis",
                    tuple(range(len(model.shape))),
                    lambda: model.record_axis,
                    lambda value: setattr(model, "record_axis", value),
                ),
                ChoiceField(
                    "layout",
                    "Interpretation",
                    tuple(ArrayLayout),
                    lambda: model.layout,
                    model.choose_layout,
                ),
                *tuple(
                    TextField(
                        name,
                        label,
                        lambda name=name: getattr(model, name),
                        lambda value, name=name: setattr(model, name, value),
                    )
                    for name, label in (
                        ("axes", "Display axes"),
                        ("channel", "Channel axis (empty for none)"),
                        ("fixed", "Fixed source coordinates"),
                    )
                ),
                ColumnPicker(
                    "support",
                    "Supporting member",
                    lambda: model.choices,
                    lambda: model.candidate,
                    lambda names: setattr(model, "candidate", names),
                    SingleSelection(),
                ),
                CommandButton("add", "Add supporting column", model.add),
                Conditional(
                    "pages",
                    lambda: len(model.supports) > 8,
                    (
                        ChoiceField(
                            "page",
                            "Supporting page",
                            lambda: tuple(
                                range(max(1, (len(model.supports) + 7) // 8))
                            ),
                            lambda: model.page,
                            lambda value: setattr(model, "page", value),
                            labels=lambda: tuple(
                                str(i + 1)
                                for i in range(max(1, (len(model.supports) + 7) // 8))
                            ),
                        ),
                    ),
                ),
                SupportingForms(model),
                CommandButton(
                    "confirm",
                    "Confirm record mapping",
                    lambda: open_records(model.build()),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.reason)
        super().render(frame)


class MappingSettings(Container):
    def __init__(
        self,
        source: NumericSourceController,
        open_records: Callable[[ArrayRecordMapping], object],
    ) -> None:
        super().__init__("mapping", ())
        self.source, self.open_records = source, open_records
        self._model: RecordMappingDraft | None = None

    def render(self, frame: FrameContext) -> None:
        model = self.source.mapping
        if model is None:
            return
        if model is not self._model:
            self.close()
            self._model = model
            self.children = (MappingForm(model, self.open_records),)
        opened = imgui.collapsing_header("Record mapping")
        target(frame, "open")
        if opened:
            super().render(frame)
