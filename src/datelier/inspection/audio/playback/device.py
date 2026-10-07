"""Lazy, typed PortAudio boundary; only explicit playback opens an output device."""

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.playback.types import (
    BLOCK_FRAMES,
    PlaybackRequest,
    RenderAction,
)

type Renderer = Callable[[NDArray[np.float32], bool], RenderAction]


class OutputDevice(Protocol):
    name: str
    latency: float

    @property
    def active(self) -> bool: ...

    def start(self) -> None: ...
    def abort(self) -> None: ...
    def close(self) -> None: ...


class _Stream(Protocol):
    latency: float
    samplerate: float

    @property
    def active(self) -> bool: ...

    def start(self) -> object: ...
    def abort(self, ignore_errors: bool = True) -> None: ...
    def close(self, ignore_errors: bool = True) -> None: ...


class _SoundDevice(Protocol):
    CallbackStop: type[Exception]
    CallbackAbort: type[Exception]

    def query_devices(self, device: str | None, kind: str) -> Mapping[str, object]: ...
    def check_output_settings(
        self, *, device: str | None, channels: int, dtype: str, samplerate: int
    ) -> None: ...
    def OutputStream(
        self,
        *,
        samplerate: int,
        blocksize: int,
        device: str | None,
        channels: int,
        dtype: str,
        latency: str,
        callback: Callable[[NDArray[np.float32], int, object, object], None],
    ) -> _Stream: ...


class SoundDeviceOutput:
    def __init__(self, request: PlaybackRequest, render: Renderer) -> None:
        # The untyped dependency is confined to this explicit output boundary.
        sd = cast(_SoundDevice, import_module("sounddevice"))
        rate = request.metadata.require_rate()
        sd.check_output_settings(
            device=request.device,
            channels=request.channels,
            dtype="float32",
            samplerate=rate,
        )
        info = sd.query_devices(request.device, "output")
        self.name = str(info["name"])

        def callback(
            output: NDArray[np.float32], frames: int, time: object, status: object
        ) -> None:
            action = render(output, bool(status))
            if action == RenderAction.FINISH:
                raise sd.CallbackStop()
            if action == RenderAction.ABORT:
                raise sd.CallbackAbort()

        self._stream = sd.OutputStream(
            samplerate=rate,
            blocksize=BLOCK_FRAMES,
            device=request.device,
            channels=request.channels,
            dtype="float32",
            latency="low",
            callback=callback,
        )
        self.latency = self._stream.latency
        if self._stream.samplerate != rate:
            self._stream.close(ignore_errors=False)
            raise ValueError("Output device changed the requested original sample rate")

    @property
    def active(self) -> bool:
        return self._stream.active

    def start(self) -> None:
        self._stream.start()

    def abort(self) -> None:
        self._stream.abort(ignore_errors=False)

    def close(self) -> None:
        self._stream.close(ignore_errors=False)


type DeviceFactory = Callable[[PlaybackRequest, Renderer], OutputDevice]
