"""One explicit slice form for NumPy members, mapped records and CPU tensors."""

from imgui_bundle import imgui

from datelier.application.sources.numeric import NumericSourceController
from datelier.application.sources.records import ArrayRecordController
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.inputs import (
    BooleanField,
    ChoiceField,
    FloatField,
    IntegerField,
    TextField,
)
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.heatmaps import Colormap


class SliceSettingsView(Container):
    def __init__(
        self,
        model: NumericSourceController,
        record: ArrayRecordController | None = None,
    ) -> None:
        self.model = model
        coordinates = tuple(
            TextField(
                name,
                label,
                lambda name=name: getattr(model.slice, name),
                lambda value, name=name: setattr(model.slice, name, value),
            )
            for name, label in (
                ("axes", "Display axes (empty for scalar)"),
                ("fixed", "Fixed coordinates (one per source axis)"),
                ("starts", "Window starts"),
                ("counts", "Window counts"),
            )
            if record is None or name in ("starts", "counts")
        )
        super().__init__(
            "slice-settings",
            (
                CommandButton("prepare", "Prepare exact slice", model.request),
                JobFeedback(
                    "job",
                    lambda: JobSnapshot(model.jobs.message, model.jobs.busy),
                    model.jobs.abandon,
                ),
                *coordinates,
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
                    ("Magnitude", "Real", "Imaginary"),
                    lambda: model.slice.component,
                    lambda value: setattr(model.slice, "component", value),
                ),
                Conditional(
                    "structured",
                    lambda: bool(model.entry and model.entry.fields),
                    (
                        ChoiceField(
                            "field",
                            "Structured field",
                            lambda: (
                                "Whole value",
                                *(model.entry.fields if model.entry else ()),
                            ),
                            lambda: model.slice.field or "Whole value",
                            lambda value: setattr(
                                model.slice,
                                "field",
                                None if value == "Whole value" else value,
                            ),
                        ),
                    ),
                ),
                ChoiceField(
                    "colormap",
                    "Colors",
                    tuple(Colormap),
                    lambda: model.slice.colormap,
                    lambda value: setattr(model.slice, "colormap", value),
                ),
                BooleanField(
                    "range",
                    "Custom display range",
                    lambda: model.slice.manual,
                    lambda value: setattr(model.slice, "manual", value),
                ),
                Conditional(
                    "bounds",
                    lambda: model.slice.manual,
                    tuple(
                        FloatField(
                            name,
                            label,
                            lambda name=name: getattr(model.slice, name),
                            lambda value, name=name: setattr(model.slice, name, value),
                            minimum=-1e300,
                            maximum=1e300,
                        )
                        for name, label in (("low", "Low"), ("high", "High"))
                    ),
                ),
                IntegerField(
                    "cache",
                    "Retained cache (MiB)",
                    lambda: model.retention_mib,
                    lambda value: setattr(model, "retention_mib", value),
                    minimum=0,
                    maximum=4096,
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(f"Exact member: {self.model.settings.member}")
        super().render(frame)
