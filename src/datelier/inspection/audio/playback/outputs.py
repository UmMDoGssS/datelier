"""Explicit worker-side device discovery; inspection/restoration never queries IO."""

from collections.abc import Mapping, Sequence
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from datelier.core import JobExecutor


@dataclass(frozen=True)
class OutputChoice:
    query: str
    channels: int


class _DeviceCatalog(Protocol):
    def query_devices(self) -> Sequence[Mapping[str, object]]: ...
    def query_hostapis(self) -> Sequence[Mapping[str, object]]: ...


def discover_outputs() -> tuple[OutputChoice, ...]:
    # Names plus API distinguish equal device names and survive index changes.
    sdk = cast(_DeviceCatalog, import_module("sounddevice"))
    hosts = sdk.query_hostapis()
    choices = []
    for device in sdk.query_devices():
        channels, host = device["max_output_channels"], device["hostapi"]
        if not isinstance(channels, int) or not isinstance(host, int):
            raise ValueError("Output device metadata is unavailable")
        if channels > 0:
            choices.append(
                OutputChoice(f"{device['name']}, {hosts[host]['name']}", channels)
            )
    return tuple(choices)


class OutputDevices:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(executor, max_workers=1, name="audio-outputs")
        self._future: Future[tuple[OutputChoice, ...]] | None = None
        self.choices: tuple[OutputChoice, ...] = ()
        self.message = "Check outputs to choose an audio device."
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request(self) -> None:
        if self.closed or self._future is not None:
            return
        self._future = self._jobs.submit(discover_outputs)
        self.message = "Checking audio output devices…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.choices = future.result()
            self.message = f"{len(self.choices)} audio output devices available."
        except Exception as error:
            self.message = f"Audio output check failed: {error}"

    def close(self, *, wait: bool = False) -> None:
        self.closed = True
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self.choices = ()
        self._jobs.shutdown(wait=wait, cancel_futures=True)
