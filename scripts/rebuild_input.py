"""Native pointer input shared by reconstructed workflow smoke checks."""

from imgui_bundle import imgui

from datelier.gui.components.probe import GuiProbe


class NativeInput:
    def __init__(self) -> None:
        self.point: tuple[float, float] | None = None
        self.entered = self.phase = 0

    def advance(self, frame: int) -> bool:
        if self.point is None:
            return False
        io = imgui.get_io()
        io.mouse_pos = imgui.ImVec2(*self.point)
        io.want_set_mouse_pos = True
        if frame - self.entered < 4:
            return True
        if self.phase < 2:
            io.add_mouse_button_event(0, self.phase == 0)
            self.phase += 1
            self.entered = frame
        else:
            self.point = None
        return True

    def find(
        self, probe: GuiProbe, suffix: tuple[str, ...]
    ) -> tuple[float, float] | None:
        return next(
            (
                p
                for key, p in probe.targets.items()
                if key.path[-len(suffix) :] == suffix
            ),
            None,
        )

    def click(self, probe: GuiProbe, suffix: tuple[str, ...], frame: int) -> bool:
        point = self.find(probe, suffix)
        if point is None:
            return False
        entry = next(
            key
            for key, value in probe.targets.items()
            if value == point and key.path[-len(suffix) :] == suffix
        )
        panel = entry.path[1]
        start, end = (
            self.find(probe, (panel, "clip-start")),
            self.find(probe, (panel, "clip-end")),
        )
        low, high = (start[1], end[1]) if start and end else (70, 540)
        if suffix[-1] == "restore":
            low, high = 40, 760
        if not low < point[1] < high:
            self.scroll(
                probe,
                panel,
                -1 if point[1] >= high else 1,
                frame,
            )
            return False
        self.point, self.entered, self.phase = point, frame, 0
        return True

    def scroll(self, probe: GuiProbe, panel: str, direction: int, frame: int) -> None:
        point = self.find(probe, (panel, "scroll"))
        if point:
            io = imgui.get_io()
            io.mouse_pos = imgui.ImVec2(*point)
            io.want_set_mouse_pos = True
            if frame % 5 == 0:
                io.add_mouse_wheel_event(0, direction)

    def click_point(self, point: tuple[float, float], frame: int) -> None:
        self.point, self.entered, self.phase = point, frame, 0
