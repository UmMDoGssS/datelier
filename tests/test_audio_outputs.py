"""Explicit output catalog discovery, stable names and cancelled publication."""

from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

from datelier.inspection.audio.playback.outputs import (
    OutputChoice,
    OutputDevices,
    discover_outputs,
)


class Catalog:
    def query_hostapis(self) -> list[dict[str, object]]:
        return [{"name": "ALSA"}, {"name": "JACK"}]

    def query_devices(self) -> list[dict[str, object]]:
        return [
            {"name": "Microphone", "max_output_channels": 0, "hostapi": 0},
            {"name": "USB audio", "max_output_channels": 2, "hostapi": 0},
            {"name": "USB audio", "max_output_channels": 8, "hostapi": 1},
        ]


def test_only_output_choices_use_stable_name_and_host_api() -> None:
    with patch(
        "datelier.inspection.audio.playback.outputs.import_module",
        return_value=Catalog(),
    ):
        assert discover_outputs() == (
            OutputChoice("USB audio, ALSA", 2),
            OutputChoice("USB audio, JACK", 8),
        )


def test_idle_catalog_is_lazy_and_close_rejects_slow_results() -> None:
    entered, release = Event(), Event()

    def slow() -> tuple[OutputChoice, ...]:
        entered.set()
        assert release.wait(5)
        return (OutputChoice("stale output, ALSA", 2),)

    jobs = OutputDevices()
    try:
        with patch("datelier.inspection.audio.playback.outputs.discover_outputs", slow):
            assert not jobs.busy and jobs.choices == ()
            jobs.request()
            assert entered.wait(5)
            jobs.close()
            assert not jobs.busy and jobs.choices == ()
            release.set()
            jobs.close(wait=True)
            jobs.poll()
            assert jobs.choices == ()
    finally:
        release.set()
        jobs.close(wait=True)


def test_output_errors_are_retryable_without_starting_playback() -> None:
    jobs = OutputDevices()
    try:
        with patch(
            "datelier.inspection.audio.playback.outputs.discover_outputs",
            side_effect=OSError("PortAudio library unavailable"),
        ):
            jobs.request()
            deadline = monotonic() + 5
            while jobs.busy and monotonic() < deadline:
                jobs.poll()
                sleep(0.001)
            assert not jobs.busy and "unavailable" in jobs.message
        with patch(
            "datelier.inspection.audio.playback.outputs.discover_outputs",
            return_value=(OutputChoice("usable output, ALSA", 2),),
        ):
            jobs.request()
            deadline = monotonic() + 5
            while jobs.busy and monotonic() < deadline:
                jobs.poll()
                sleep(0.001)
            assert not jobs.busy and jobs.choices == (
                OutputChoice("usable output, ALSA", 2),
            )
    finally:
        jobs.close(wait=True)
