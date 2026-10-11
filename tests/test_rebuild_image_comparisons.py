"""Mapped payloads, independent scopes/drafts and idle comparison restoration."""

from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from test_rebuild_comparisons import until

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.images.profiles import PixelScope
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def test_mapped_image_comparison_and_original_record_navigation(tmp_path: Path) -> None:
    array_path, png = tmp_path / "images.npz", tmp_path / "other.png"
    np.savez_compressed(
        array_path,
        images=np.array(
            [np.full((2, 2, 3), 10), np.full((2, 2, 3), 30)], dtype=np.uint8
        ),
        labels=np.array([2, 1]),
    )
    Image.new("RGB", (4, 2), (50, 60, 70)).save(png)
    originals = array_path.read_bytes(), png.read_bytes()
    editor = EditorController()
    try:
        owner = editor.active
        owner.open(array_path)
        other = editor.new_file(png)
        until(
            editor,
            lambda: owner.inspection is not None and other.inspection is not None,
        )
        mapping = ArrayRecordMapping(
            "images",
            layout=ArrayLayout.IMAGE,
            display_axes=(1, 2),
            channel_axis=3,
            supporting=(SupportingArray("labels", "label"),),
        )
        named = owner.record_views.open_array(owner, mapping)
        until(editor, lambda: named.inspection is not None)
        named.editor.request(Sort(("label",)))
        until(editor, lambda: not named.editor.busy)
        model = editor.compare.images
        model.map_files((named.identity, other.identity))
        assert tuple(s.profile.column for s in model.draft.sources) == (
            "images",
            "path",
        )
        model.draft = replace(model.draft, bins=2)
        model.prepare()
        until(editor, lambda: model.active is not None)
        result = model.active
        assert result
        assert result.profiles[0].records["row_id"].to_list() == [1, 0]
        assert (
            result.profiles[0].mapping == mapping
            and result.profiles[0].summaries[0].mean == 20
        )
        assert model.plot and len(model.plot.series) == 2
        model.draft = replace(
            model.draft,
            sources=tuple(
                replace(
                    s,
                    profile=replace(s.profile, pixels=PixelScope.SAMPLE, pixel_count=1),
                )
                for s in model.draft.sources
            ),
        )
        editor.poll()
        assert model.active is result and model.changed
        model.open_record(result, 0, 0)
        assert editor.current is named and named.selection.row_ids == {1}
        assert (
            owner.selection.row_ids == frozenset()
            and named.records.settings.mapped_payload
        )
        assert named.views.tab == "Inspect" and named.table.target_row == 1
        model.prepare()
        until(editor, lambda: model.active is not None)
        assert model.active and [p.profiled_pixels for p in model.active.profiles] == [
            2,
            1,
        ]
        model.view = replace(
            model.view, height=0, tab="Colors", mode="RGB", dtype="|u1", channel="R"
        )
        saved = capture_session(editor)
        saved.workspace.validate()
        workspace = tmp_path / "saved.json"
        save_snapshot(workspace, saved, False)
        owner.record_views.close_view(named.identity)
        editor.poll()
        assert model.active is None and len(model.recipes[0].sources) == 1
        assert originals == (array_path.read_bytes(), png.read_bytes())
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(reopened, lambda: not reopened.workspace.busy)
        model = reopened.compare.images
        assert (
            model.jobs.started == 0 and model.active is None and model.view.height == 0
        )
        assert (
            model.view.tab == "Colors"
            and model.draft.sources[0].profile.pixels == PixelScope.SAMPLE
        )
        assert all(
            f.images.profile_jobs.active is None and not f.audio.player.snapshot.request
            for f in reopened.all_files
        )
    finally:
        reopened.close()
