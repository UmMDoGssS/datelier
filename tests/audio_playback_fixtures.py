"""Deterministic output devices for playback and editor ownership checks."""

from threading import Event

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.playback.device import Renderer
from datelier.inspection.audio.playback.types import PlaybackRequest, RenderAction


class FakeDevice:
    name = "deterministic output"
    latency = 0.03

    def __init__(self, request: PlaybackRequest, render: Renderer) -> None:
        self.request, self.render = request, render
        self.active = self.closed = False
        self.closing = Event()
        self.close_gate: Event | None = None
        self.start_error = self.close_error = ""

    def start(self) -> None:
        if self.start_error:
            raise RuntimeError(self.start_error)
        self.active = True

    def pump(self, frames: int = 512, *, status: bool = False) -> NDArray[np.float32]:
        assert self.active
        output = np.empty((frames, self.request.channels), dtype=np.float32)
        action = self.render(output, status)
        if action != RenderAction.CONTINUE:
            self.active = False
        return output

    def abort(self) -> None:
        self.active = False

    def close(self) -> None:
        self.closing.set()
        if self.close_gate is not None:
            assert self.close_gate.wait(5)
        self.active, self.closed = False, True
        if self.close_error:
            raise RuntimeError(self.close_error)


class Devices:
    def __init__(self) -> None:
        self.devices: list[FakeDevice] = []

    def create(self, request: PlaybackRequest, render: Renderer) -> FakeDevice:
        assert all(device.closed for device in self.devices)
        device = FakeDevice(request, render)
        self.devices.append(device)
        return device
