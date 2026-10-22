"""Session-only numeric axis ranges and scale controls shared by 2D plots.

Apply validates both ranges before changing the view; wheel zoom/pan remain
available afterward. Linear and symmetric-log scales support signed data; log10
requires positive ranges. Category/temporal axes retain their native labels.
Plot/column changes reset these transient axis edits.
"""

from abc import ABC, abstractmethod

from imgui_bundle import imgui, implot

from datelier.application.exploration import AxisScale, AxisState
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.inputs import ChoiceField, FloatField
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.components.layout.groups import Conditional
from datelier.gui.components.layout.viewport import ViewportContent
from datelier.gui.components.native import target

SCALES = (implot.Scale_.linear, implot.Scale_.sym_log, implot.Scale_.log10)


class AxisFields(Container):
    def __init__(self, model: AxisState, index: int) -> None:
        axis = "XY"[index]
        super().__init__(
            axis,
            (
                ChoiceField(
                    "scale",
                    f"{axis} scale",
                    tuple(AxisScale),
                    lambda: AxisScale(model.draft_scales[index]),
                    lambda v: model.draft_scales.__setitem__(index, v),
                    ("Linear", "Symmetric log", "Log 10"),
                ),
                FloatField(
                    "minimum",
                    f"{axis} minimum",
                    lambda: model.draft[index][0],
                    lambda v: model.draft[index].__setitem__(0, v),
                    -1e300,
                    1e300,
                ),
                FloatField(
                    "maximum",
                    f"{axis} maximum",
                    lambda: model.draft[index][1],
                    lambda v: model.draft[index].__setitem__(1, v),
                    -1e300,
                    1e300,
                ),
            ),
        )


class AxisControls(Container):
    def __init__(self, model: AxisState) -> None:
        self.model = model

        def accept() -> None:
            model.accept()
            imgui.close_current_popup()

        self.apply = CommandButton("apply", "Apply ranges", accept)
        super().__init__(
            "axes",
            (
                *(
                    Conditional(
                        f"axis-{i}",
                        lambda i=i: model.enabled[i],
                        (AxisFields(model, i),),
                    )
                    for i in range(2)
                ),
                self.apply,
            ),
        )

    def render(self, frame: FrameContext) -> None:
        if not any(self.model.enabled):
            return
        if imgui.button("Axes##edit"):
            self.model.begin_edit()
            self.apply.error = ""
            imgui.open_popup("Axis ranges")
        target(frame, "open")
        imgui.set_next_window_size((260, 0), imgui.Cond_.appearing)
        if imgui.begin_popup("Axis ranges"):
            super().render(frame)
            for i, axis in enumerate("xy"):
                frame.measure(
                    f"{axis}-draft", (self.model.draft[i][0], self.model.draft[i][1])
                )
            frame.measure(
                "scales",
                (float(self.model.draft_scales[0]), float(self.model.draft_scales[1])),
            )
            imgui.end_popup()


def apply_axes(model: AxisState) -> None:
    request = model.take_request()
    for i, axis in enumerate((implot.ImAxis_.x1, implot.ImAxis_.y1)):
        if model.enabled[i]:
            implot.setup_axis_scale(axis, SCALES[model.scales[i]])
            if request:
                implot.setup_axis_limits(axis, *request[i], imgui.Cond_.always)


def observe_axes(model: AxisState, frame: FrameContext) -> None:
    limits = implot.get_plot_limits()
    model.observe(((limits.x.min, limits.x.max), (limits.y.min, limits.y.max)))
    for i, axis in enumerate("xy"):
        frame.measure(f"{axis}-range", model.limits[i])


class AxisPlot(ViewportContent, ABC):
    """Numeric plot families share draft controls without owning file sessions."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.axes = AxisState()
        self.tools = AxisControls(self.axes)

    @abstractmethod
    def plot_scope(self) -> object: ...

    def numeric_axes(self) -> tuple[bool, bool]:
        return True, True

    @abstractmethod
    def render_plot(self, frame: FrameContext) -> None: ...

    def render(self, frame: FrameContext) -> None:
        if self.axes.bind(self.plot_scope(), self.numeric_axes()):
            self.fit = True
        if self.fit:
            self.axes.pending = False
        self.tools.render(frame.child(self.tools.key))
        self.render_plot(frame)

    def render_children(self, frame: FrameContext) -> None:
        super().render(frame)

    def close(self) -> None:
        self.tools.close()
        super().close()
