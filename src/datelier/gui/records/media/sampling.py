"""Scoped image sampling for the verified Linux OpenGL renderer.

Bundle omits ImDrawList::AddCallback from its Python bindings. This narrow ABI
bridge calls that exported public C++ method with opaque pointers and uses only
standard OpenGL sampler functions; it never reads ImGui's internal structures.
Callbacks stay owned until GUI disposal, after the queued draws have rendered.
"""

import ctypes as ct
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.util import find_spec

from imgui_bundle import hello_imgui

_DRAW_CALLBACK = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_void_p)


class _OpenGlCallbacks:
    def __init__(self) -> None:
        spec = find_spec("imgui_bundle._imgui_bundle")
        if spec is None or spec.origin is None:
            raise RuntimeError("Cannot locate the native image sampling bridge")
        self.bundle = ct.CDLL(spec.origin)
        self.gl = ct.CDLL("libGL.so.1")
        self.get_draw_list = self.bundle._ZN5ImGui17GetWindowDrawListEv
        self.get_draw_list.argtypes, self.get_draw_list.restype = [], ct.c_void_p
        self.add_callback = (
            self.bundle._ZN10ImDrawList11AddCallbackEPFvPKS_PK9ImDrawCmdEPvm
        )
        self.add_callback.argtypes = [
            ct.c_void_p,
            _DRAW_CALLBACK,
            ct.c_void_p,
            ct.c_size_t,
        ]
        self.add_callback.restype = None
        self.gl.glGenSamplers.argtypes = [ct.c_int, ct.POINTER(ct.c_uint)]
        self.gl.glDeleteSamplers.argtypes = [ct.c_int, ct.POINTER(ct.c_uint)]
        self.gl.glSamplerParameteri.argtypes = [ct.c_uint, ct.c_uint, ct.c_int]
        self.gl.glBindSampler.argtypes = [ct.c_uint, ct.c_uint]
        self.gl.glGetIntegerv.argtypes = [ct.c_uint, ct.POINTER(ct.c_int)]
        for name in (
            "glGenSamplers",
            "glDeleteSamplers",
            "glSamplerParameteri",
            "glBindSampler",
            "glGetIntegerv",
        ):
            getattr(self.gl, name).restype = None
        self.sampler, self.previous = ct.c_uint(), ct.c_int()
        self.gl.glGenSamplers(1, ct.byref(self.sampler))
        if not self.sampler.value:
            raise RuntimeError("Cannot create the nearest image sampler")
        # MIN/MAG_FILTER = NEAREST; WRAP_S/T = CLAMP_TO_EDGE.
        for parameter, value in (
            (0x2801, 0x2600),
            (0x2800, 0x2600),
            (0x2802, 0x812F),
            (0x2803, 0x812F),
        ):
            self.gl.glSamplerParameteri(self.sampler.value, parameter, value)
        self.nearest = _DRAW_CALLBACK(self._nearest)
        self.restore = _DRAW_CALLBACK(self._restore)

    def _nearest(self, _draw_list: object, _command: object) -> None:
        self.gl.glGetIntegerv(0x8919, ct.byref(self.previous))  # SAMPLER_BINDING
        self.gl.glBindSampler(0, self.sampler.value)

    def _restore(self, _draw_list: object, _command: object) -> None:
        self.gl.glBindSampler(0, self.previous.value)

    def close(self) -> None:
        if self.sampler.value:
            self.gl.glDeleteSamplers(1, ct.byref(self.sampler))
            self.sampler.value = 0


class NearestSampling:
    def __init__(self) -> None:
        self._bridge: _OpenGlCallbacks | None = None

    @contextmanager
    def draw(self) -> Iterator[None]:
        if self._bridge is None:
            if "OpenGL3" not in hello_imgui.get_backend_description():
                raise RuntimeError("Sharp image sampling requires the OpenGL3 renderer")
            self._bridge = _OpenGlCallbacks()
        bridge = self._bridge
        draw_list = bridge.get_draw_list()
        bridge.add_callback(draw_list, bridge.nearest, None, 0)
        try:
            yield
        finally:
            bridge.add_callback(draw_list, bridge.restore, None, 0)

    def close(self) -> None:
        if self._bridge:
            self._bridge.close()
            self._bridge = None
