"""Explicit complete corpus jobs and independent single-record publication."""

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import polars as pl

from datelier.core import SharedWorkers
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.profiles.prepare import (
    PreparedTextProfile,
    prepare_profile,
)
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
)
from datelier.io.importing import load_file


def wait(jobs: TextJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy, jobs.message


def test_exact_profile_command_keeps_all_types_and_survives_record_navigation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.csv"
    pl.DataFrame(
        {"id": range(100), "text": [f"word{i} common" for i in range(100)]}
    ).write_csv(source)
    dataset = load_file(source).dataset
    jobs = TextJobs()
    try:
        jobs.settings = TextSettings(
            "text", TextSource.INLINE, scope=TextScope(CorpusMode.COLLECTION)
        )
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        assert jobs.profile is None and not jobs.busy
        jobs.request_profile()
        wait(jobs)
        profile = jobs.profile
        assert profile and profile.profile.tokens == 200
        assert (
            profile.profile.vocabulary_size == profile.profile.frequencies.height == 101
        )
        assert len(profile.frequency_labels) == 12 and sum(profile.length_counts) == 100
        assert profile.profile.hapax == 100
        jobs.settings = replace(jobs.settings, position=5)
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        jobs.request_document()
        wait(jobs)
        assert jobs.active and jobs.active.document.origin.row_id == 5
        assert jobs.profile is profile
        document = jobs.active
        jobs.request_profile()
        wait(jobs)
        assert jobs.active is document
        profile = jobs.profile
        assert profile is not None
        jobs.settings = replace(jobs.settings, position=7)
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        assert jobs.active is None and jobs.profile is profile
        jobs.settings = replace(
            jobs.settings, tokens=TokenSettings(TokenMode.CHARACTER)
        )
        jobs.bind(dataset, "file", ReferenceSettings(), None)
        assert jobs.profile is None
    finally:
        jobs.close()


def test_linked_scope_revision_and_closed_views_reject_profiles(tmp_path: Path) -> None:
    source = tmp_path / "corpus.csv"
    source.write_text("id,text\n1,one two\n2,three\n")
    dataset = load_file(source).dataset
    started, release = Event(), Event()
    workers = SharedWorkers()
    jobs = TextJobs(workers)
    try:
        jobs.settings = TextSettings(
            "text", TextSource.INLINE, scope=TextScope(CorpusMode.SELECTION)
        )
        jobs.bind(dataset, "first", ReferenceSettings(), None, (0,))
        jobs.request_profile()
        wait(jobs)
        assert jobs.profile and jobs.profile.profile.tokens == 2
        jobs.bind(dataset, "first", ReferenceSettings(), None, (1,))
        assert jobs.profile is None
        original = prepare_profile

        def slow(*args: object) -> PreparedTextProfile:
            started.set()
            assert release.wait(3)
            # Use an independent event to force a late successful result.
            from datelier.inspection.text.profiles.corpus import TextProgress

            return original(
                dataset,
                "first",
                jobs.settings,
                (1,),
                ReferenceSettings(),
                None,
                Event(),
                TextProgress(),
            )

        with patch("datelier.inspection.text.jobs.prepare_profile", side_effect=slow):
            jobs.request_profile()
        assert started.wait(3)
        pending = jobs._profile
        assert pending is not None
        jobs.bind(
            dataset.with_role("text", None), "first", ReferenceSettings(), None, (1,)
        )
        jobs.close()
        release.set()
        pending.result(3)
        jobs.poll()
        assert jobs.profile is None and jobs.active is None
    finally:
        release.set()
        jobs.close()
        workers.shutdown()
