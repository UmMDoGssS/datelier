"""Original audio preparation and safe playback lifetime outside GUI rendering."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.audio_collection import AudioCollectionController
from datelier.application.media_input import MediaController, MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.inspection.audio.jobs import AudioJobs
from datelier.inspection.audio.playback.controller import AudioPlayback, PlaybackPhase
from datelier.inspection.audio.playback.requests import playback_request
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioLocator, AudioMetadata
from datelier.inspection.audio.view_jobs import SignalViewJobs


class AudioController(MediaController):
    def __init__(
        self, executor: Executor | None = None, playback: AudioPlayback | None = None
    ) -> None:
        self._source: MediaInput | None = None
        self.jobs = AudioJobs(executor)
        self.signal = SignalViewJobs(executor)
        self.collection = AudioCollectionController(executor)
        self.channel_statistics: tuple[tuple[object, ...], ...] = ()
        self.signal_statistics: tuple[tuple[object, ...], ...] = ()
        self._profile = None
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
        self.settings = replace(
            self.settings,
            collection=replace(
                self.settings.collection,
                array_sample_rate=self.settings.array_sample_rate,
            ),
        )
        self.collection.settings = self.settings.collection
        self.collection.sync(source)
        if self._profile is not self.jobs.profile:
            self._profile = self.jobs.profile
            profile = self._profile
            self.channel_statistics = (
                tuple(
                    (
                        c.channel + 1,
                        c.minimum,
                        c.maximum,
                        c.peak,
                        c.mean,
                        c.rms,
                        c.clipped,
                        c.silent,
                        c.finite,
                        c.nonfinite,
                        c.samples,
                    )
                    for c in profile.channels
                )
                if profile
                else ()
            )
            self.signal_statistics = (
                (
                    ("Frames", profile.frames),
                    ("Duration (s)", profile.duration),
                    ("All-channel silence (s)", profile.silence_duration),
                    ("Longest silence (frames)", profile.longest_silence_frames),
                    ("Nonfinite frames", profile.nonfinite_frames),
                    ("Clipping rails", profile.clipping_bounds),
                    ("Silence threshold", profile.thresholds.silence),
                )
                if profile
                else ()
            )

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
        mapping = record_mapping(active, column)
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

    @property
    def sample_rate(self) -> int | None:
        return self.jobs.metadata[1].sample_rate if self.jobs.metadata else None

    @property
    def start_seconds(self) -> float:
        return self.settings.range.start / (self.sample_rate or 1)

    @property
    def stop_seconds(self) -> float:
        stop = self.settings.range.stop
        if stop is None and self.jobs.metadata:
            stop = self.jobs.metadata[1].frames
        return (stop or 0) / (self.sample_rate or 1)

    def set_start_seconds(self, value: float) -> None:
        if self.sample_rate:
            self.settings = replace(
                self.settings,
                range=replace(
                    self.settings.range, start=max(0, round(value * self.sample_rate))
                ),
            )

    def set_stop_seconds(self, value: float) -> None:
        if self.sample_rate:
            self.settings = replace(
                self.settings,
                range=replace(
                    self.settings.range, stop=max(0, round(value * self.sample_rate))
                ),
            )

    def abandon_signal(self) -> None:
        self.signal.abandon()
        self.signal.message = "Signal work abandoned; executing work cannot publish."

    def abandon_profile(self) -> None:
        self.jobs.abandon_profile()
        self.jobs.message = "Profile work abandoned; executing work cannot publish."

    def request_samples(self) -> None:
        if self._source:
            self.jobs.request_window(self.settings.range, self._source.arrays)

    def request_collection(self, column: str) -> None:
        if self._source:
            mapping = record_mapping(self._source.active, column)
            self.settings = replace(
                self.settings,
                collection=replace(
                    self.settings.collection,
                    column=mapping.member if mapping else column,
                    array_sample_rate=self.settings.array_sample_rate,
                ),
            )
            self.collection.settings = self.settings.collection
            self.collection.sync(self._source)
            self.collection.request()

    def play(self) -> None:
        if self._source is None or self.jobs.metadata is None:
            raise ValueError("Choose an audio record before playback")
        request = playback_request(self.jobs.metadata, self.settings)
        cursor = self.settings.playback.seek_frame
        if cursor is not None:
            request = replace(
                request,
                start_frame=min(
                    max(cursor, request.range.start),
                    request.range.stop or request.metadata.frames,
                ),
            )
        self.player.play(
            request,
            self._source.arrays,
            volume=self.settings.playback.volume,
        )

    def pause(self) -> None:
        self.player.pause(self.player.snapshot.phase != PlaybackPhase.PAUSED)

    def stop(self) -> None:
        self.player.stop(self._source.file_id if self._source else None)

    def seek(self, frame: int) -> None:
        self.settings = replace(
            self.settings, playback=replace(self.settings.playback, seek_frame=frame)
        )
        self.player.seek(frame)

    def set_volume(self, volume: float) -> None:
        self.settings = replace(
            self.settings, playback=replace(self.settings.playback, volume=volume)
        )
        self.player.set_volume(volume)

    def close(self, file_id: str | None = None) -> None:
        self._source = None
        if self._owns_player:
            self.player.close(wait=False)
        elif file_id is not None:
            self.player.stop(file_id)
        self.signal.close()
        self.jobs.close()
        self.collection.close()
        self._profile = None
        self.channel_statistics = self.signal_statistics = ()
