"""Reference settings, literal value mappings and bounded metadata lists."""

from imgui_bundle import imgui

from datelier.application.media.records import ReferenceController
from datelier.application.tabular import SingleSelection
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.inputs import (
    BooleanField,
    ColumnPicker,
    IntegerField,
    TextField,
)
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.layout.groups import Collapsible
from datelier.gui.components.native import target


class MappingList(Component):
    def __init__(self, model: ReferenceController) -> None:
        super().__init__("mappings")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        mappings = self.model.jobs.settings.mappings
        if not mappings:
            return
        if imgui.begin_child("mappings", (-1, 120)):
            clipper = imgui.ListClipper()
            clipper.begin(len(mappings), imgui.get_frame_height_with_spacing())
            while clipper.step():
                for i in range(clipper.display_start, clipper.display_end):
                    mapping = mappings[i]
                    imgui.push_id(i)
                    if imgui.small_button("Remove"):
                        self.model.remove(mapping)
                    target(frame.child(str(i)), "remove")
                    imgui.same_line()
                    imgui.text_unformatted(f"{mapping.column}: {mapping.value}")
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(mapping.path)
                    imgui.pop_id()
        imgui.end_child()


class ReferenceSettings(Container):
    def __init__(self, model: ReferenceController) -> None:
        self.model = model
        super().__init__(
            "reference-settings",
            (
                JobFeedback(
                    "status",
                    lambda: JobSnapshot(
                        model.jobs.message,
                        model.jobs.busy,
                        f"{model.jobs.progress.count:,} files discovered · "
                        f"retained CPU {model.jobs.retained_bytes / 1048576:.2f} MiB",
                    ),
                ),
                BooleanField(
                    "thumbnails",
                    "Image thumbnails",
                    lambda: model.thumbnails,
                    lambda v: setattr(model, "thumbnails", v),
                ),
                CommandButton("retry", "Retry discovery / previews", model.jobs.retry),
                CommandButton(
                    "abandon",
                    "Abandon discovery",
                    model.jobs.abandon_index,
                    lambda: model.jobs.busy,
                ),
                TextField(
                    "roots",
                    "Roots (one per line; blank = nearby)",
                    lambda: model.roots,
                    lambda v: setattr(model, "roots", v),
                    True,
                ),
                TextField(
                    "extensions",
                    "Extensions (comma-separated)",
                    lambda: model.extensions,
                    lambda v: setattr(model, "extensions", v),
                ),
                IntegerField(
                    "size",
                    "Thumbnail pixels",
                    lambda: model.size,
                    lambda v: setattr(model, "size", v),
                    32,
                    512,
                ),
                IntegerField(
                    "cpu",
                    "CPU cache (MiB)",
                    lambda: model.cpu_mib,
                    lambda v: setattr(model, "cpu_mib", v),
                    1,
                    256,
                ),
                IntegerField(
                    "gpu",
                    "GPU cache (MiB)",
                    lambda: model.gpu_mib,
                    lambda v: setattr(model, "gpu_mib", v),
                    1,
                    128,
                ),
                CommandButton("configure", "Apply reference settings", model.configure),
                Collapsible(
                    "mapping",
                    "Reference mappings",
                    (
                        ColumnPicker(
                            "column",
                            "Reference column",
                            lambda: model.columns,
                            lambda: (model.column,) if model.column else (),
                            lambda names: setattr(
                                model, "column", next(iter(names), None)
                            ),
                            SingleSelection(),
                        ),
                        TextField(
                            "value",
                            "Original cell value",
                            lambda: model.value,
                            lambda v: setattr(model, "value", v),
                        ),
                        TextField(
                            "path",
                            "Exact file path",
                            lambda: model.path,
                            lambda v: setattr(model, "path", v),
                        ),
                        CommandButton("apply", "Use mapped file", model.apply_mapping),
                        MappingList(model),
                    ),
                ),
            ),
        )
