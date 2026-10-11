"""Typed format drafts, transactional reloads and idle draft restoration."""

from pathlib import Path

import pytest
from test_rebuild_comparisons import until

from datelier.application.imports import ImportController
from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.io.loading import LoadPhase
from datelier.io.types import (
    ArrayOptions,
    CheckpointOptions,
    CsvOptions,
    ImportFormat,
    ImportOptions,
    JsonOptions,
    MediaOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions import SourceDraft
from datelier.workspace.sessions.jobs import save_snapshot


@pytest.mark.parametrize(
    "format, options",
    [
        (
            ImportFormat.CSV,
            CsvOptions(
                separator=";",
                quote_char=None,
                null_values=("N|A", "", "two\nlines"),
                infer_schema_length=None,
                skip_rows=1,
            ),
        ),
        (ImportFormat.TSV, CsvOptions(separator="\t", has_header=False)),
        (ImportFormat.JSON, JsonOptions(True)),
        (ImportFormat.JSONL, JsonOptions(True)),
        (ImportFormat.PARQUET, ParquetOptions(("a|b", "two\nlines"))),
        (
            ImportFormat.XML,
            XmlOptions(
                ".//n:row",
                (("n", "urn:namespace|value"),),
                False,
                False,
                ("N|A",),
                False,
                True,
            ),
        ),
        (
            ImportFormat.MEDIA,
            MediaOptions(True, False, ("a|b.txt",), (("a|b.txt", 5),)),
        ),
        (ImportFormat.OBJECT, ObjectOptions("json", ("rows", 2), True)),
        (ImportFormat.ARRAY, ArrayOptions(True, 18000, record_table=False)),
        (ImportFormat.CHECKPOINT, CheckpointOptions(1000, 9)),
    ],
)
def test_option_families_preserve_exact_hidden_and_literal_recipe_fields(
    format: ImportFormat,
    options: ImportOptions,
) -> None:
    model = ImportController(lambda _: None)
    saved = SourceDraft("/unused/source", format, options)
    model.bind(saved)
    assert model.capture() == saved
    if format == ImportFormat.CSV:
        model.csv.separator = ","
        changed = model.capture()
        assert changed and isinstance(changed.options, CsvOptions)
        assert changed.options.null_values == ("N|A", "", "two\nlines")
    if format == ImportFormat.MEDIA:
        model.media.refresh()
        changed = model.capture()
        assert changed and isinstance(changed.options, MediaOptions)
        assert changed.options.manifest is None and not changed.options.line_counts


def test_drafts_are_independent_and_invalid_submissions_never_reach_loader() -> None:
    submitted: list[SourceDraft] = []
    model = ImportController(submitted.append)
    model.path = "/unused/data.csv"
    model.csv.separator = "::"
    with pytest.raises(ValueError, match="single"):
        model.request()
    assert not submitted
    model.csv.separator = ";"
    model.format = ImportFormat.TSV
    model.request()
    assert submitted[-1].options == CsvOptions(separator="\t")
    model.format = ImportFormat.CSV
    model.request()
    assert submitted[-1].options == CsvOptions(separator=";")
    model.blocked = True
    with pytest.raises(ValueError, match="recovery"):
        model.request()
    model.blocked, model.closed = False, True
    with pytest.raises(ValueError):
        model.request()
    assert len(submitted) == 2


def test_failed_reload_keeps_recipe_and_restores_attempt_settings_without_reload(
    tmp_path: Path,
) -> None:
    source, missing, session = (
        tmp_path / "data.csv",
        tmp_path / "missing.csv",
        tmp_path / "session.json",
    )
    source.write_text("x;y\n1;10\n3;30\n2;20\n")
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.current
        file.open(source, CsvOptions(separator=";"))
        until(editor, lambda: file.explorer.active is not None)
        file.editor.request(Sort(("x",), True))
        until(editor, lambda: not file.editor.busy and file.explorer.active is not None)
        revision = file.loader.revision
        file.imports.csv.separator = "::"
        with pytest.raises(ValueError, match="single"):
            file.imports.request()
        assert file.loader.revision == revision
        file.imports.csv.separator, file.imports.path = ";", str(missing)
        file.imports.request()
        other = editor.new_file()
        until(editor, lambda: not file.imports.busy)
        assert editor.current is other
        assert file.loader.status.phase == LoadPhase.FAILED
        assert file.title == source.name
        assert file.loader.revision == revision and file.inspection
        assert file.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        editor.activate(file.identity)
        snapshot = capture_session(editor)
        assert snapshot.workspace.files[0].recipe
        assert snapshot.workspace.files[0].import_settings == SourceDraft(
            str(missing), ImportFormat.CSV, CsvOptions(separator=";")
        )
        save_snapshot(session, snapshot, False)
        assert source.read_bytes() == original
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(session)
        until(
            reopened,
            lambda: (
                not reopened.workspace.busy
                and reopened.current.explorer.active is not None
            ),
        )
        file = reopened.current
        assert file.inspection and file.inspection.dataset.source.path == source
        assert file.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        assert file.imports.path == str(missing) and file.imports.csv.separator == ";"
        assert file.loader.status.phase == LoadPhase.READY
        file.editor.request(Sort(("x",)))
        until(reopened, lambda: not file.editor.busy)
        assert file.imports.path == str(missing)
        assert not file.analysis.jobs.results and not file.text.corpus.busy
        assert source.read_bytes() == original
    finally:
        reopened.close()


def test_automatic_default_import_retains_non_record_json_hierarchy_fallback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "object.json"
    source.write_text('{"rows":[{"x":1}],"name":"inspection"}')
    editor = EditorController()
    try:
        file = editor.current
        file.imports.path = str(source)
        file.imports.request()
        until(editor, lambda: file.objects.root is not None)
        assert (
            file.inspection and file.inspection.imported.format == ImportFormat.OBJECT
        )
        assert file.imports.format == ImportFormat.OBJECT
        assert not file.record_views.files and not file.analysis.jobs.results
    finally:
        editor.close()
