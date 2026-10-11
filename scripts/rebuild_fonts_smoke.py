"""Actual native glyph/texture coverage for the Phase 12 multilingual fixtures."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe

TEXT = "Tiếng Việt e\u0301 · Ελληνικά · 中文日本語 · 🙂🚀"


def main() -> None:
    output = Path("/tmp/datelier-rebuild-fonts")
    verified = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal verified
        imgui.set_next_window_size((650, 160), imgui.Cond_.always)
        imgui.set_next_window_pos((410, 410), imgui.Cond_.always)
        imgui.begin("Unicode font verification")
        imgui.text_unformatted(TEXT)
        default_font = imgui.get_font()
        default_missing = tuple(
            ch
            for ch in TEXT
            if not ch.isspace() and not default_font.is_glyph_in_font(ord(ch))
        )
        imgui.text(f"Default {imgui.get_font_size()} missing: {default_missing}")
        imgui.push_font(None, 20)
        imgui.text_unformatted(TEXT)
        font = imgui.get_font()
        missing = tuple(
            ch for ch in TEXT if not ch.isspace() and not font.is_glyph_in_font(ord(ch))
        )
        imgui.text(f"Missing glyphs: {missing}")
        baked = font.get_font_baked(imgui.get_font_size())
        imgui.pop_font()
        imgui.end()
        if evidence.frames > 15:
            assert not default_missing, default_missing
            assert not missing, missing
            assert all(
                baked.find_glyph_no_fallback(ord(ch)) is not None
                for ch in TEXT
                if not ch.isspace()
            )
            for ch in "🙂🚀":
                glyph = baked.find_glyph_no_fallback(ord(ch))
                assert glyph is not None and glyph.is_visible()
                assert glyph.x1 > glyph.x0 and glyph.y1 > glyph.y0
            verified = True
            hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory() as directory:
        evidence = run_gui(
            smoke_frames=50,
            on_probe_frame=frame,
            preferences_path=Path(directory) / "prefs.json",
        )
    assert verified
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / "unicode-fonts.png"
    )
    report = {
        "frames": evidence.frames,
        "text": TEXT,
        "missing_glyphs": [],
        "visible_outline_emoji": True,
    }
    (output / "unicode-fonts.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
