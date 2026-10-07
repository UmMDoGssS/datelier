"""Real ImGui input capture/dispatch shared by native audio acceptance workflows."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from imgui_bundle import imgui


class NativeControls:
    def __init__(self) -> None:
        self.points: dict[str, tuple[float, float]] = {}
        self.clips: dict[str, tuple[float, float]] = {}
        self.scroll: dict[str, tuple[float, float]] = {}
        self.phase = self.entered = 0

    def capture(self, label: str, numeric: bool = False) -> None:
        low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.points[label] = (
            low.x + 30 if numeric else (low.x + high.x) / 2,
            (low.y + high.y) / 2,
        )
        position, size = imgui.get_window_pos(), imgui.get_window_size()
        self.clips[label] = (position.y + 25, position.y + size.y - 20)
        self.scroll[label] = (position.x + size.x - 7, position.y + size.y / 2)

    @contextmanager
    def patched(self) -> Iterator[None]:
        button, checkbox, integer = imgui.button, imgui.checkbox, imgui.input_int
        double, radio, header = (
            imgui.input_double,
            imgui.radio_button,
            imgui.collapsing_header,
        )

        def capture_button(label: str, size: imgui.ImVec2 | None = None) -> bool:
            value = button(label, size)
            self.capture(label)
            return value

        def capture_checkbox(label: str, value: bool) -> tuple[bool, bool]:
            updated = checkbox(label, value)
            self.capture(label)
            return updated

        def capture_int(
            label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0
        ) -> tuple[bool, int]:
            updated = integer(label, value, step, step_fast, flags)
            self.capture(label, True)
            return updated

        def capture_double(
            label: str,
            value: float,
            step: float = 0,
            step_fast: float = 0,
            format: str = "%.6f",
            flags: int = 0,
        ) -> tuple[bool, float]:
            updated = double(label, value, step, step_fast, format, flags)
            self.capture(label, True)
            return updated

        def capture_radio(label: str, active: bool) -> bool:
            updated = radio(label, active)
            self.capture(label)
            return updated

        def capture_header(label: str, flags: int = 0) -> bool:
            updated = header(label, flags)
            self.capture(label)
            return updated

        with ExitStack() as stack:
            for name, callback in (
                ("button", capture_button),
                ("checkbox", capture_checkbox),
                ("input_int", capture_int),
                ("input_double", capture_double),
                ("radio_button", capture_radio),
                ("collapsing_header", capture_header),
            ):
                stack.enter_context(patch.object(imgui, name, callback))
            yield

    def advance(self, target: str, frame: int) -> bool:
        """Click/scroll/type through ImGui IO; never fabricate widget results."""
        age, io = frame - self.entered, imgui.get_io()
        key = target.rsplit("=", 1)[0]
        if self.phase == 0 and age > 9 and key in self.points:
            top, bottom = self.clips[key]
            if not top <= self.points[key][1] <= bottom:
                io.mouse_pos = imgui.ImVec2(*self.scroll[key])
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(0, -2 if self.points[key][1] > bottom else 2)
                self.entered = frame
                return False
            io.mouse_pos = imgui.ImVec2(*self.points[key])
            io.want_set_mouse_pos = True
            io.add_mouse_button_event(0, True)
            self.phase, self.entered = 1, frame
        elif self.phase == 1 and age > 3:
            io.add_mouse_button_event(0, False)
            if "=" not in target:
                self.phase, self.entered = 0, frame
                return True
            self.phase, self.entered = 2, frame
        elif self.phase == 2 and age > 3:
            io.add_key_event(imgui.Key.left_ctrl, True)
            io.add_key_event(imgui.Key.a, True)
            self.phase, self.entered = 3, frame
        elif self.phase == 3 and age > 3:
            io.add_key_event(imgui.Key.a, False)
            io.add_key_event(imgui.Key.left_ctrl, False)
            io.add_input_characters_utf8(target.rsplit("=", 1)[1])
            self.phase, self.entered = 4, frame
        elif self.phase == 4 and age > 3:
            io.add_key_event(imgui.Key.enter, True)
            self.phase, self.entered = 5, frame
        elif self.phase == 5 and age > 3:
            io.add_key_event(imgui.Key.enter, False)
            self.phase, self.entered = 6, frame
        elif self.phase == 6 and age > 7:
            self.phase, self.entered = 0, frame
            return True
        return False
