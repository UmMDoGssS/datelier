"""Local Linux motion fixture: preserve ImGui deltas while the OS pointer moves."""

import ctypes as ct
from typing import cast

from imgui_bundle import imgui
from rebuild_input import NativeInput


class NativeMotion(NativeInput):
    def __init__(self) -> None:
        super().__init__()
        self._x11 = ct.CDLL("libX11.so.6")
        self._x11.XOpenDisplay.argtypes, self._x11.XOpenDisplay.restype = (
            [ct.c_char_p],
            ct.c_void_p,
        )
        self._x11.XDefaultRootWindow.argtypes, self._x11.XDefaultRootWindow.restype = (
            [ct.c_void_p],
            ct.c_ulong,
        )
        self._x11.XWarpPointer.argtypes = [
            ct.c_void_p,
            ct.c_ulong,
            ct.c_ulong,
            ct.c_int,
            ct.c_int,
            ct.c_uint,
            ct.c_uint,
            ct.c_int,
            ct.c_int,
        ]
        self._x11.XWarpPointer.restype = ct.c_int
        self._x11.XQueryPointer.argtypes = [
            ct.c_void_p,
            ct.c_ulong,
            ct.POINTER(ct.c_ulong),
            ct.POINTER(ct.c_ulong),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_int),
            ct.POINTER(ct.c_uint),
        ]
        self._x11.XQueryPointer.restype = ct.c_int
        self._x11.XFlush.argtypes, self._x11.XFlush.restype = [ct.c_void_p], ct.c_int
        self._x11.XCloseDisplay.argtypes, self._x11.XCloseDisplay.restype = (
            [ct.c_void_p],
            ct.c_int,
        )
        self._display = cast(int, self._x11.XOpenDisplay(None))
        if not self._display:
            raise RuntimeError("The native motion gate requires a local X11 display")
        self._root = cast(int, self._x11.XDefaultRootWindow(self._display))
        self._offset: tuple[int, int] | None = None

    def advance(self, frame: int) -> bool:
        if self.point is None:
            return False
        io = imgui.get_io()
        io.want_set_mouse_pos = False
        if self._offset is None:
            root, child = ct.c_ulong(), ct.c_ulong()
            x, y, wx, wy, mask = (
                ct.c_int(),
                ct.c_int(),
                ct.c_int(),
                ct.c_int(),
                ct.c_uint(),
            )
            self._x11.XQueryPointer(
                self._display,
                self._root,
                ct.byref(root),
                ct.byref(child),
                ct.byref(x),
                ct.byref(y),
                ct.byref(wx),
                ct.byref(wy),
                ct.byref(mask),
            )
            self._offset = (
                x.value - round(io.mouse_pos.x),
                y.value - round(io.mouse_pos.y),
            )
        self._x11.XWarpPointer(
            self._display,
            0,
            self._root,
            0,
            0,
            0,
            0,
            round(self.point[0]) + self._offset[0],
            round(self.point[1]) + self._offset[1],
        )
        self._x11.XFlush(self._display)
        if frame - self.entered < 4:
            return True
        if self.phase == 0:
            io.add_mouse_button_event(0, True)
            self.phase, self.entered = 1, frame
        elif self.phase == 1 and self._drag_end is not None:
            self.point = self._drag_end
            self.phase, self.entered = 2, frame
        elif self.phase in (1, 2):
            io.add_mouse_button_event(0, False)
            self.phase, self.entered = 3, frame
        else:
            self.point = self._drag_end = None
        return True

    def close(self) -> None:
        if self._display:
            self._x11.XCloseDisplay(self._display)
            self._display = 0
