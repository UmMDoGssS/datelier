"""Original audio preparation and safe playback lifetime outside GUI rendering."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.media_input import MediaController, MediaInput
from datelier.inspection.audio.jobs import AudioJobs
from datelier.inspection.audio.playback.controller import AudioPlayback, PlaybackPhase
from datelier.inspection.audio.playback.requests import playback_request
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioLocator, AudioMetadata
from datelier.inspection.audio.view_jobs import SignalViewJobs
from datelier.io.types import ArrayOptions


class AudioController(MediaController):
    def __init__(
        self, executor: Executor | None = None, playback: AudioPlayback | None = None
    ) -> None:
        self._source: MediaInput | None = None
        self.jobs = AudioJobs(executor)
        self.signal = SignalViewJobs(executor)
        self.player = (
            playback if playback is not None else AudioPlayback(executor=executor)
        )
        self._owns_player = playback is None
        self.settings = AudioSettings()

    def sync(self, source: MediaInput) -> None:
        self._source = source
        active = source.active
        self.jobs.sync(
            source.file_id,
            source.view_name,
            active.dataset.revision if active else None,
            source.references,
            source.index,
        )
        self.jobs.cpu_bytes = self.settings.cpu_bytes
        self.jobs.poll()
        self.player.devices.poll()
        records = source.records
        prepared = self.jobs.metadata
        if (
            prepared is not None
            and prepared[0].catalog is not None
            and (prepared[1].sample_rate != self.settings.array_sample_rate)
        ):
            prepared = None
        if prepared is not None and records is not None:
            focus = min(source.inspect.focus, max(0, len(records.row_ids) - 1))
            if (
                not len(records.row_ids)
                or int(records.row_ids[focus]) != prepared[0].origin.row_id
            ):
                prepared = None
        self.sync_playback(source.file_id, prepared, self.settings)
        self.signal.bind(self.jobs.metadata)
        self.signal.poll()

    def sync_playback(
        self,
        file_id: str,
        prepared: tuple[AudioLocator, AudioMetadata] | None,
        settings: AudioSettings,
    ) -> None:
        state = self.player.snapshot
        request = state.request
        if (
            request is not None
            and request.locator.origin.file_id == file_id
            and state.phase
            in (PlaybackPhase.STARTING, PlaybackPhase.PLAYING, PlaybackPhase.PAUSED)
        ):
            if prepared is None or replace(
                request, start_frame=None
            ) != playback_request(prepared, settings):
                self.player.stop(file_id)

    def request_record(self, column: str, position: int) -> None:
        source = self._source
        active = source.active if source else None
        if active is None:
            return
        options = active.imported.options
        mapping = (
            options.mapping_for(active.imported.array_catalog, column)
            if isinstance(options, ArrayOptions)
            else None
        )
        self.jobs.request_record(
            active.dataset,
            column,
            position,
            active.imported.array_catalog,
            mapping,
            self.settings.array_sample_rate,
        )

    def request_profile(self) -> None:
        if self._source:
            self.jobs.request_profile(
                self.settings.range, self.settings.thresholds, self._source.arrays
            )

    def request_signal(self) -> None:
        if self._source:
            settings = self.settings
            self.signal.request(
                settings.range,
                settings.channel,
                settings.view,
                self._source.arrays,
                settings.cpu_bytes,
            )

    def close(self, file_id: str | None = None) -> None:
        self._source = None
        if self._owns_player:
            self.player.close(wait=False)
        elif file_id is not None:
            self.player.stop(file_id)
        self.signal.close()
        self.jobs.close()
