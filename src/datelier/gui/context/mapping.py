"""Confirmed array record mappings reuse selectors and typed field controls."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.columns import ColumnChoice, MultiSelection
from datelier.application.sources.numeric import NumericSourceController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import ChoiceField, IntegerField, TextField
from datelier.gui.context.slices import indices
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping


class MappingSettings(Container):
    def __init__(
        self,
        model: NumericSourceController,
        open_records: Callable[[ArrayRecordMapping], object],
    ) -> None:
        self.model, self.open_records = model, open_records
        self.axes, self.fixed, self.channel = "", "", ""
        self._member = ""
        super().__init__(
            "mapping",
            (
                IntegerField(
                    "record-axis",
                    "Record axis",
                    lambda: model.mapping.record_axis,
                    lambda value: setattr(
                        model, "mapping", replace(model.mapping, record_axis=value)
                    ),
                    maximum=63,
                ),
                ChoiceField(
                    "layout",
                    "Interpretation",
                    tuple(ArrayLayout),
                    lambda: model.mapping.layout,
                    model.choose_layout,
                ),
                TextField(
                    "axes",
                    "Display axes",
                    lambda: self.axes,
                    lambda value: setattr(self, "axes", value),
                ),
                TextField(
                    "channel",
                    "Channel axis (empty for none)",
                    lambda: self.channel,
                    lambda value: setattr(self, "channel", value),
                ),
                TextField(
                    "fixed",
                    "Fixed source coordinates",
                    lambda: self.fixed,
                    lambda value: setattr(self, "fixed", value),
                ),
                ColumnPicker(
                    "support",
                    "Aligned supporting members",
                    lambda: tuple(
                        ColumnChoice(name, "Array") for name in model.support_choices
                    ),
                    lambda: model.supporting,
                    lambda names: setattr(model, "supporting", names),
                    MultiSelection(256),
                ),
                CommandButton("confirm", "Confirm record mapping", self.confirm),
            ),
        )

    def confirm(self) -> None:
        try:
            channel = int(self.channel) if self.channel.strip() else None
        except ValueError as error:
            raise ValueError("Channel axis must be an integer or empty") from error
        self.model.mapping = replace(
            self.model.mapping,
            display_axes=indices(self.axes),
            fixed=indices(self.fixed),
            channel_axis=channel,
        )
        self.open_records(self.model.confirmed_mapping())

    def render(self, frame: FrameContext) -> None:
        if not self.model.entries or not self.model.mapping.member:
            return
        if imgui.collapsing_header("Record mapping"):
            if self._member != self.model.mapping.member:
                self._member = self.model.mapping.member
                self.axes = ",".join(map(str, self.model.mapping.display_axes))
                self.fixed = ",".join(map(str, self.model.mapping.fixed))
                self.channel = (
                    str(self.model.mapping.channel_axis)
                    if self.model.mapping.channel_axis is not None
                    else ""
                )
            imgui.text_wrapped(self.model.mapping_reason)
            super().render(frame)
