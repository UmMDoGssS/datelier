"""One explicit bounded slice editor for NumPy arrays and CPU tensors."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.sources.numeric import NumericSourceController
from datelier.application.sources.records import ArrayRecordController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.fields import (
    BooleanField,
    ChoiceField,
    FloatField,
    IntegerField,
    TextField,
)
from datelier.inspection.heatmaps import Colormap


def indices(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as error:
        raise ValueError("Use comma-separated integer axes or positions") from error


class SliceSettingsView(Container):
    def __init__(
        self,
        model: NumericSourceController,
        record: ArrayRecordController | None = None,
    ) -> None:
        super().__init__("slice-settings", ())
        self.model = model
        self.record = record
        self.axes = self.fixed = self.starts = self.counts = ""
        self._member = ""
        self.manual = False
        self.low, self.high = 0.0, 1.0
        fields = tuple(
            TextField(
                name,
                label,
                lambda name=name: getattr(self, name),
                lambda value, name=name: setattr(self, name, value),
            )
            for name, label in (
                ("axes", "Display axes (0-based)"),
                ("fixed", "Fixed coordinates (one per source axis)"),
                ("starts", "Window starts"),
                ("counts", "Window counts"),
            )
            if record is None or name in ("starts", "counts")
        )
        self.children = (
            CommandButton("prepare", "Prepare exact slice", self.request),
            JobFeedback(
                "job",
                lambda: JobSnapshot(model.jobs.message, model.jobs.busy),
                model.jobs.abandon,
            ),
            *fields,
            *(
                (
                    IntegerField(
                        "channel",
                        "Channel",
                        lambda: record.channel,
                        lambda value: setattr(record, "channel", value),
                    ),
                )
                if record
                else ()
            ),
            ChoiceField(
                "component",
                "Complex values",
                lambda: ("Magnitude", "Real", "Imaginary"),
                lambda: model.settings.component,
                lambda value: setattr(
                    model, "settings", replace(model.settings, component=value)
                ),
            ),
            ChoiceField(
                "field",
                "Structured field",
                lambda: ("Whole value", *self.fields()),
                lambda: model.settings.field or "Whole value",
                lambda value: setattr(
                    model,
                    "settings",
                    replace(
                        model.settings, field=None if value == "Whole value" else value
                    ),
                ),
            ),
            ChoiceField(
                "colormap",
                "Colors",
                lambda: tuple(Colormap),
                lambda: model.settings.colormap,
                lambda value: setattr(
                    model, "settings", replace(model.settings, colormap=value)
                ),
            ),
            BooleanField(
                "range",
                "Display range",
                lambda: self.manual,
                lambda value: setattr(self, "manual", value),
            ),
            FloatField(
                "low",
                "Low",
                lambda: self.low,
                lambda value: setattr(self, "low", value),
                minimum=-1e300,
                maximum=1e300,
            ),
            FloatField(
                "high",
                "High",
                lambda: self.high,
                lambda value: setattr(self, "high", value),
                minimum=-1e300,
                maximum=1e300,
            ),
            IntegerField(
                "cache",
                "Retained cache (MiB)",
                lambda: model.retention_mib,
                lambda value: setattr(model, "retention_mib", value),
                minimum=0,
                maximum=4096,
            ),
        )

    def fields(self) -> tuple[str, ...]:
        return next(
            (
                e.fields
                for e in self.model.entries
                if e.name == self.model.settings.member
            ),
            (),
        )

    def request(self) -> None:
        settings = replace(
            self.model.settings,
            axes=self.model.settings.axes if self.record else indices(self.axes),
            fixed=self.model.settings.fixed if self.record else indices(self.fixed),
            starts=indices(self.starts),
            counts=indices(self.counts),
            scalar=not (
                self.model.settings.axes if self.record else indices(self.axes)
            ),
            value_range=(self.low, self.high) if self.manual else None,
        )
        settings.validate()
        self.model.jobs.set_retention(self.model.retention_mib * 1024 * 1024)
        self.model.jobs.request(settings)

    def render(self, frame: FrameContext) -> None:
        settings = self.model.settings
        if settings.member != self._member:
            self._member = settings.member
            for name in ("axes", "fixed", "starts", "counts"):
                setattr(self, name, ",".join(map(str, getattr(settings, name))))
            self.manual = settings.value_range is not None
            self.low, self.high = settings.value_range or (0, 1)
        imgui.text_wrapped(f"Exact member: {settings.member}")
        super().render(frame)
