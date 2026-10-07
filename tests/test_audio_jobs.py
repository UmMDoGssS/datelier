"""Queued/running audio jobs cannot publish into changed or closed file views."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import soundfile as sf

from datelier.inspection.audio.jobs import AudioJobs
from datelier.inspection.audio.sources import prepare_metadata
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore
from datelier.io.media import load_media


def gated[**P, T](
    function: Callable[P, T], entered: Event, release: Event
) -> Callable[P, T]:
    def delayed(*args: P.args, **kwargs: P.kwargs) -> T:
        entered.set()
        assert release.wait(5)
        return function(*args, **kwargs)

    return delayed


def wait(jobs: AudioJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_audio_jobs_read_only_headers_until_window_command(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, np.ones(100) * 0.25, 8000, subtype="DOUBLE")
    table = load_media(path).dataset
    jobs, store = AudioJobs(), ArrayStore()
    try:
        jobs.sync("a", "records", table.revision, ReferenceSettings(), None)
        jobs.request_record(table, "path", 0)
        wait(jobs)
        assert jobs.metadata is not None and jobs.active is None
        assert jobs.metadata[0].origin.file_id == "a"
        jobs.request_window(AudioRange(20, 40), store)
        wait(jobs)
        assert jobs.active is not None and jobs.active.raw.shape == (20, 1)
        np.testing.assert_array_equal(jobs.active.raw, np.full((20, 1), 0.25))
        jobs.sync("a", "another-view", table.revision, ReferenceSettings(), None)
        assert jobs.active is jobs.metadata is None
        jobs.request_record(table, "missing", 0)
        wait(jobs)
        assert jobs.metadata is None and "Cannot inspect audio" in jobs.message
    finally:
        jobs.close()
        store.close()


def test_running_metadata_replacement_and_closure_keep_equal_row_ids_separate(
    tmp_path: Path,
) -> None:
    tables = []
    for name in ("a", "b"):
        path = tmp_path / (name + ".wav")
        sf.write(path, np.zeros(20), 8000)
        tables.append(load_media(path).dataset)
    entered, release = Event(), Event()

    delayed = gated(prepare_metadata, entered, release)

    with ThreadPoolExecutor(max_workers=1) as pool:
        jobs = AudioJobs(pool)
        try:
            jobs.sync("a", "records", tables[0].revision, ReferenceSettings(), None)
            with patch("datelier.inspection.audio.jobs.prepare_metadata", delayed):
                jobs.request_record(tables[0], "path", 0)
                assert entered.wait(5)
            jobs.sync("b", "records", tables[1].revision, ReferenceSettings(), None)
            jobs.request_record(tables[1], "path", 0)
            release.set()
            wait(jobs)
            assert jobs.metadata is not None
            assert (
                jobs.metadata[0].origin.file_id == "b"
                and jobs.metadata[0].origin.row_id == 0
            )
            entered.clear()
            release.clear()
            jobs.abandon()
            with patch("datelier.inspection.audio.jobs.prepare_metadata", delayed):
                jobs.request_record(tables[1], "path", 0)
                assert entered.wait(5)
            jobs.close()
            release.set()
            pool.shutdown(wait=True)
            jobs.poll()
            assert jobs.metadata is jobs.active is None
            jobs.request_record(tables[1], "path", 0)
            assert not jobs.busy
        finally:
            release.set()
            jobs.close()


def test_close_during_decode_releases_decoder_and_discards_window(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, np.zeros(100), 8000)
    table = load_media(path).dataset
    entered, release = Event(), Event()
    store = ArrayStore()
    with ThreadPoolExecutor(max_workers=1) as pool:
        jobs = AudioJobs(pool)
        try:
            jobs.sync("a", "records", table.revision, ReferenceSettings(), None)
            jobs.request_record(table, "path", 0)
            wait(jobs)
            with patch.object(
                sf.SoundFile, "read", gated(sf.SoundFile.read, entered, release)
            ):
                jobs.request_window(AudioRange(0, 100), store)
                assert entered.wait(5)
                jobs.close()
                release.set()
                pool.shutdown(wait=True)
            jobs.poll()
            assert jobs.active is jobs.metadata is None and not jobs.busy
            with sf.SoundFile(path) as reopened:
                assert reopened.read().shape == (100,)
        finally:
            release.set()
            jobs.close()
            store.close()
