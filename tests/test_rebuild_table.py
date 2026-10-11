"""Prepared table roles, atomic display drafts and revision-scoped references."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_rebuild_comparisons import until

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.core.column_roles import ColumnRole
from datelier.inspection.presentation import NumericScale, cell_style
from datelier.inspection.references.types import ReferenceMapping, Resolution
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def test_table_styles_reference_mapping_and_idle_restoration(tmp_path: Path) -> None:
    source, session = tmp_path / "data.csv", tmp_path / "session.json"
    source.write_text("x,image\n1.0,missing.png\n2.0,missing.png\n3.0,missing.png\n")
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.current
        file.open(source)
        until(
            editor,
            lambda: file.inspection is not None and file.table.snapshot is not None,
        )
        snapshot = file.table.snapshot
        assert snapshot
        assert (
            snapshot.columns[0].role == ColumnRole.NUMERIC
            and snapshot.columns[0].bounds
        )
        assert snapshot.columns[1].reference
        styles = file.table.presentation
        styles.settings = replace(
            styles.settings, scale=NumericScale.CUSTOM, badges=False
        )
        styles.minimum, styles.maximum = 2, 1
        with pytest.raises(ValueError, match="finite"):
            styles.apply()
        assert styles.settings.minimum == 0 and styles.settings.maximum == 1
        styles.maximum = 4
        styles.apply()
        assert file.inspection
        cell = file.inspection.first_page.cells[0][0]
        assert (
            cell_style(cell, snapshot.columns[0].bounds, styles.settings).marker == "<"
        )
        refs = file.reference_tools
        refs.thumbnails = False
        refs.choose_target("image", "missing.png", Resolution("missing.png"))
        refs.map_target(str(tmp_path / "chosen.png"))
        assert file.references.settings.mappings == (
            ReferenceMapping("image", "missing.png", str(tmp_path / "chosen.png")),
        )
        file.editor.request(Sort(("x",), True))
        until(editor, lambda: not file.editor.busy)
        with pytest.raises(ValueError, match="changed"):
            refs.map_target(str(tmp_path / "wrong.png"))
        save_snapshot(session, capture_session(editor), False)
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
                and reopened.current.table.snapshot is not None
            ),
        )
        file = reopened.current
        assert file.table.presentation.settings.scale == NumericScale.CUSTOM
        assert (file.table.presentation.minimum, file.table.presentation.maximum) == (
            2,
            4,
        )
        assert (
            not file.table.presentation.settings.badges
            and not file.reference_tools.thumbnails
        )
        assert file.references.settings.mappings[0].value == "missing.png"
        assert file.inspection and file.inspection.dataset.row_ids.to_list() == [
            2,
            1,
            0,
        ]
        assert not file.analysis.jobs.results and source.read_bytes() == original
    finally:
        reopened.close()


def test_array_payload_cells_are_not_file_references(tmp_path: Path) -> None:
    source = tmp_path / "images.npz"
    np.savez(
        source,
        images=np.arange(24, dtype=np.uint8).reshape(3, 2, 4),
        labels=np.array([1, 2, 3]),
    )
    editor = EditorController()
    try:
        file = editor.current
        file.open(source)
        until(editor, lambda: file.table.snapshot is not None)
        assert file.table.snapshot
        image = next(c for c in file.table.snapshot.columns if c.name == "images")
        assert (
            image.role in (ColumnRole.IMAGE, ColumnRole.LIST_NUMERIC)
            and not image.reference
        )
        assert "images" not in {c.name for c in file.table.reference_columns}
    finally:
        editor.close()
