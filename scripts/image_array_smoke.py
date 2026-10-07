"""Mapped image Inspect preserves source indices and supporting rows after sorting."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.pipeline.operations import Sort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-array")
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-image-array-") as directory:
        root = Path(directory)
        source = root / "images.npz"
        raw = np.zeros((3, 64, 64, 3), dtype=np.uint8)
        for record in range(3):
            raw[record] = (10 * (record + 1), 5, 9)
        np.savez_compressed(source, images=raw, labels=np.array([3, 1, 2]))
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        stage = entered = 0
        next_pixel = (0.0, 0.0)
        profile_pixels: dict[str, tuple[float, float]] = {}
        original_button = imgui.button
        origins: list[int] = []
        values: list[tuple[object, ...]] = []

        def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
            nonlocal next_pixel
            result = original_button(label, size)
            if label == "Next record":
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                next_pixel = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
            if label in ("Profile mapped images", "Prepare image profile"):
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                profile_pixels[label] = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
            return result

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered
            owner = editor.active
            active = owner.loader.active
            if active is None:
                return
            view = owner.record_views.active(owner)
            age = evidence.frames - entered
            params, io = hello_imgui.get_runner_params(), imgui.get_io()
            if stage == 0 and owner.arrays.catalog is not None:
                assert owner.arrays.store.extractions == 0
                owner.record_views.open_array(
                    owner,
                    ArrayRecordMapping(
                        "images",
                        layout=ArrayLayout.IMAGE,
                        display_axes=(1, 2),
                        channel_axis=3,
                        supporting=(SupportingArray("labels", "label"),),
                    ),
                )
                stage, entered = 1, evidence.frames
            elif stage == 1 and view is not owner and view.loader.active is not None:
                assert owner.arrays.store.extractions == 1
                view.editor.request(Sort(("label",)))
                stage, entered = 2, evidence.frames
            elif stage == 2 and not view.editor.busy and age > 8:
                assert view.loader.active is not None
                assert view.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
                from dataclasses import replace

                view.inspect.settings = replace(view.inspect.settings, gallery=False)
                view.exploration.tab = "Inspect"
                params.docking_params.focus_dockable_window("Explore")
                stage, entered = 3, evidence.frames
            elif stage in (3, 7) and view.images.jobs.active is not None and age > 12:
                prepared = view.images.jobs.active
                expected = 1 if stage == 3 else 2
                assert prepared.locator.origin.row_id == expected
                assert (
                    prepared.locator.origin.file_id == view.identity != owner.identity
                )
                assert prepared.pixel(0, 0) == (10 * (expected + 1), 5, 9)
                page = view.inspect.jobs.get(view.inspect.settings.focus)
                assert page is not None
                card = page.cards[view.inspect.settings.focus - page.start]
                assert card.row_id == expected
                assert next(
                    field.text for field in card.fields if field.name == "label"
                ) == str(expected)
                origins.append(expected)
                values.append(prepared.pixel(0, 0) or ())
                if stage == 3:
                    io.mouse_pos = imgui.ImVec2(*next_pixel)
                    io.want_set_mouse_pos = True
                    stage, entered = 4, evidence.frames
                else:
                    assert owner.arrays.store.extractions == 2
                    assert view.images.jobs.store.decodes == 0
                    # A shorter dock may need only part of the 64×64 record.
                    assert 0 < view.images.canvas.retained_bytes <= 64 * 64 * 4
                    view.exploration.tab = "Profiles"
                    stage, entered = 8, evidence.frames
            elif stage == 4 and age > 4:
                io.add_mouse_button_event(0, True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 4:
                io.add_mouse_button_event(0, False)
                stage, entered = 7, evidence.frames
            elif stage in (8, 11) and age > 8:
                target = (
                    "Profile mapped images" if stage == 8 else "Prepare image profile"
                )
                if target in profile_pixels:
                    io.mouse_pos = imgui.ImVec2(*profile_pixels[target])
                    io.want_set_mouse_pos = True
                    stage, entered = stage + 1, evidence.frames
            elif stage in (9, 12) and age > 4:
                io.add_mouse_button_event(0, True)
                stage, entered = stage + 1, evidence.frames
            elif stage in (10, 13) and age > 4:
                io.add_mouse_button_event(0, False)
                stage, entered = stage + 1, evidence.frames
            elif (
                stage == 14 and age > 8 and view.images.profile_jobs.active is not None
            ):
                profile = view.images.profile_jobs.active
                assert profile.ready == 3 and profile.profiled_pixels == 3 * 64 * 64
                assert profile.records["row_id"].to_list() == [1, 2, 0]
                assert (
                    next(s for s in profile.summaries if s.key.name == "R").mean == 20
                )
                assert owner.arrays.store.extractions == 2
                params.app_shall_exit = True
                stage = 15

        with patch.object(imgui, "button", new=button):
            evidence = run_gui(
                source,
                smoke_frames=700,
                on_editor_frame=frame,
                preferences_path=root / "prefs.json",
            )
        assert stage == 15
        assert before == hashlib.sha256(source.read_bytes()).hexdigest()
        args.output.mkdir(parents=True, exist_ok=True)
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            args.output / "image-array-profile.png"
        )
        p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
        assert p95 < 33, p95
        report = {
            "frames": evidence.frames,
            "source_rows": origins,
            "pixels": values,
            "supporting_alignment": True,
            "source_preserved": True,
            "frame_p95_ms": p95,
            "native_profile_command": True,
            "profile_source_rows": [1, 2, 0],
            "profile_red_mean": 20,
            "profile_pixels": 3 * 64 * 64,
        }
        (args.output / "image-array-profile-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
