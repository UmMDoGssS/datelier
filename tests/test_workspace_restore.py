"""Source relinking, atomic replay, and asynchronous publication invariants."""

import os
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import pytest

from datelier.io.importing import load_file
from datelier.io.types import ImportFormat, ImportOptions, ImportResult
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Comparison, Filter, Sort
from datelier.workspace_jobs import WorkspaceJobs
from datelier.workspace_restore import RestoredWorkspace, SourceIssue, restore_workspace
from datelier.workspace_types import Workspace
from datelier.workspaces import reference_source, save_workspace


def saved_recipe(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "data.csv"
    source.write_text("x\n3\n1\n2\n")
    imported = load_file(source)
    workspace = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        (Sort(("x",)), Filter("x", Comparison.GT, 1)),
        1,
    )
    path = tmp_path / "project.datelier"
    save_workspace(path, workspace)
    return path, source


def await_job(jobs: WorkspaceJobs, revision: object = None) -> RestoredWorkspace | None:
    from typing import cast

    from datelier.core.dataset import DatasetRevision

    deadline = monotonic() + 5
    result = None
    while jobs.busy and monotonic() < deadline:
        result = jobs.poll(cast(DatasetRevision | None, revision)) or result
        sleep(0.001)
    assert not jobs.busy
    return result


def test_restore_retains_undo_redo_and_source_identity(tmp_path: Path) -> None:
    path, source = saved_recipe(tmp_path)
    restored = restore_workspace(path)
    assert restored.pipeline.current.table["x"].to_list() == [1, 2, 3]
    assert restored.inspection.first_page.row_ids == (1, 2, 0)
    assert restored.pipeline.redo().current.row_ids.to_list() == [2, 0]
    assert restored.pipeline.undo().current.row_ids.to_list() == [0, 1, 2]
    assert restored.pipeline.source.source.path == source


def test_missing_source_relinks_with_identical_content(tmp_path: Path) -> None:
    path, source = saved_recipe(tmp_path)
    moved = tmp_path / "moved.csv"
    source.rename(moved)
    with pytest.raises(SourceIssue, match="missing"):
        restore_workspace(path)
    restored = restore_workspace(path, relink=moved)
    assert restored.pipeline.source.source.path == moved
    assert restored.workspace.source.path == str(moved)


def test_content_change_detected_even_with_same_size_and_timestamp(
    tmp_path: Path,
) -> None:
    path, source = saved_recipe(tmp_path)
    stat = source.stat()
    source.write_text("x\n9\n8\n7\n")
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(SourceIssue, match="content changed"):
        restore_workspace(path)
    restored = restore_workspace(path, accept_changed=True)
    assert restored.pipeline.current.table["x"].to_list() == [7, 8, 9]
    assert (
        restored.workspace.source.sha256
        != reference_source(load_file(source).dataset.source).sha256 + "different"
    )


def test_workspace_and_source_can_move_together(tmp_path: Path) -> None:
    path, source = saved_recipe(tmp_path)
    folder = tmp_path / "moved"
    folder.mkdir()
    source.rename(folder / source.name)
    path.rename(folder / path.name)
    assert restore_workspace(folder / path.name).pipeline.current.table[
        "x"
    ].to_list() == [1, 2, 3]


def test_bad_replay_is_rejected_before_publication_including_redo(
    tmp_path: Path,
) -> None:
    path, _ = saved_recipe(tmp_path)
    restored = restore_workspace(path)
    workspace = replace(restored.workspace, history=(Sort(("missing",)),), cursor=0)
    save_workspace(path, workspace)
    with pytest.raises(ValueError, match="Unknown column"):
        restore_workspace(path)


def test_failed_and_obsolete_jobs_cannot_replace_active_workspace(
    tmp_path: Path,
) -> None:
    path, source = saved_recipe(tmp_path)
    active = load_file(source).dataset
    jobs = WorkspaceJobs()
    try:
        jobs.request_restore(path, active.revision)
        assert await_job(jobs, active.revision) is not None
        jobs.request_restore(tmp_path / "missing.datelier", active.revision)
        assert await_job(jobs, active.revision) is None
        assert "failed" in jobs.message.lower()
        jobs.request_restore(path, active.revision)
        changed = active.with_rows(active.table, active.row_ids)
        assert await_job(jobs, changed.revision) is None
        assert "obsolete" in jobs.message
        source.unlink()
        jobs.request_restore(path, active.revision)
        assert await_job(jobs, active.revision) is None
        assert jobs.issue is not None
    finally:
        jobs.close()
    with pytest.raises(ValueError, match="closed"):
        jobs.request_restore(path, None)


def test_background_save_captures_recipe_without_ml_results(tmp_path: Path) -> None:
    from datelier.analysis_types import AnalysisRequest
    from datelier.inspection.exploration import PlotSettings
    from datelier.workspace_types import WorkspaceViews

    path, source = saved_recipe(tmp_path)
    imported = load_file(source)
    pipeline = Pipeline.start(imported.dataset).apply(Sort(("x",)))
    jobs = WorkspaceJobs()
    try:
        jobs.request_save(
            path,
            pipeline,
            imported,
            (AnalysisRequest(("x",)),),
            PlotSettings(),
            WorkspaceViews(),
        )
        await_job(jobs, pipeline.current.revision)
        assert jobs.saved is None and "exists" in jobs.message
        jobs.request_save(
            path,
            pipeline,
            imported,
            (AnalysisRequest(("x",)),),
            PlotSettings(),
            WorkspaceViews(),
            overwrite=True,
        )
        await_job(jobs, pipeline.current.revision)
        assert jobs.saved is not None
        restored = restore_workspace(path)
        assert restored.workspace.analysis == (AnalysisRequest(("x",)),)
        assert restored.pipeline.current.row_ids.to_list() == [1, 2, 0]
    finally:
        jobs.close()


def test_source_mutation_during_restore_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.workspace_restore as restoring

    path, source = saved_recipe(tmp_path)
    original = restoring.load_file

    def changing_load(
        selected: Path,
        options: ImportOptions | None = None,
        *,
        format: ImportFormat | None = None,
    ) -> ImportResult:
        result = original(selected, options, format=format)
        source.write_text("x\n9\n8\n7\n")
        return result

    monkeypatch.setattr(restoring, "load_file", changing_load)
    with pytest.raises(ValueError, match="changed while restoring"):
        restore_workspace(path)


def test_newer_restore_bypasses_abandoned_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from threading import Event

    import datelier.workspace_jobs as background

    path, _ = saved_recipe(tmp_path)
    original = background.restore_workspace
    started, release = Event(), Event()
    old = tmp_path / "old.datelier"

    def delayed_restore(
        selected: Path, *, relink: Path | None = None, accept_changed: bool = False
    ) -> RestoredWorkspace:
        if selected == old:
            started.set()
            assert release.wait(5)
        return original(path, relink=relink, accept_changed=accept_changed)

    monkeypatch.setattr(background, "restore_workspace", delayed_restore)
    jobs = WorkspaceJobs()
    try:
        jobs.request_restore(old, None)
        assert started.wait(5)
        jobs.request_restore(path, None)
        restored = await_job(jobs)
        assert restored is not None
        release.set()
        assert jobs.poll(None) is None
    finally:
        release.set()
        jobs.close()


@pytest.mark.parametrize("format", list(ImportFormat))
def test_each_import_format_reopens_with_exact_options_and_replay(
    tmp_path: Path, format: ImportFormat
) -> None:
    import polars as pl

    from datelier.io.types import (
        CsvOptions,
        JsonOptions,
        ParquetOptions,
        XmlOptions,
    )
    from datelier.pipeline.types import DerivedColumn

    table = pl.DataFrame({"x": [3, 1, 2], "y": [9, 5, 7]})
    source = tmp_path / "source.data"  # saved format overrides extension
    options: ImportOptions
    if format in (ImportFormat.CSV, ImportFormat.TSV):
        separator = ";" if format == ImportFormat.CSV else "\t"
        table.write_csv(source, separator=separator)
        options = CsvOptions(separator=separator, infer_schema_length=None)
    elif format == ImportFormat.PARQUET:
        table.with_columns(pl.lit("unused").alias("extra")).write_parquet(source)
        options = ParquetOptions(("y", "x"))
    elif format in (ImportFormat.JSON, ImportFormat.JSONL):
        if format == ImportFormat.JSON:
            table.write_json(source)
        else:
            table.write_ndjson(source)
        options = JsonOptions(read_as_text=True)
    else:
        source.write_text(
            '<root xmlns:n="urn:rows">'
            "<n:r><x>3</x><y>9</y></n:r>"
            "<n:r><x>1</x><y>5</y></n:r>"
            "<n:r><x>2</x><y>7</y></n:r></root>"
        )
        options = XmlOptions("./n:r", (("n", "urn:rows"),), include_attributes=False)
    before = source.read_bytes()
    imported = load_file(source, options, format=format)
    pipeline = (
        Pipeline.start(imported.dataset)
        .apply(Sort(("x",)))
        .apply(DerivedColumn("copy", 'col("y")'))
    )
    workspace = Workspace(
        reference_source(imported.dataset.source),
        format,
        options,
        pipeline.history,
        pipeline.cursor,
    )
    path = tmp_path / "session.datelier"
    save_workspace(path, workspace)
    restored = restore_workspace(path)
    assert restored.pipeline.current.table.equals(pipeline.current.table)
    assert restored.pipeline.current.row_ids.to_list() == [1, 2, 0]
    assert restored.inspection.imported.options == options
    assert restored.inspection.imported.format == format
    assert source.read_bytes() == before
