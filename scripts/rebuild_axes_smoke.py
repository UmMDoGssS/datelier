"""Native range/scale edits, free zoom, fitting and categorical-axis protection."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput, NativeText

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.plotting.categories import CategoryRepresentation


def measure(probe: GuiProbe, suffix: tuple[str, ...]) -> tuple[float, float]:
    return next(
        v for k, v in probe.measurements.items() if k.path[-len(suffix) :] == suffix
    )


def close_to(actual: tuple[float, float], expected: tuple[float, float]) -> None:
    assert np.allclose(actual, expected), (actual, expected)


def main() -> None:
    with TemporaryDirectory(prefix="datelier-axes-") as directory:
        source = Path(directory) / "ranges.csv"
        source.write_text(
            "x,y,g\n1.0,10.0,a\n2.0,20.0,b\n3.0,30.0,a\n4.0,40.0,b\n5.0,50.0,a\n"
        )
        original = source.read_bytes()
        native, text = NativeInput(), NativeText()
        stage = entered = 0
        done = False
        y_before = (0.0, 0.0)
        zoom_point: tuple[float, float] | None = None

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, y_before, zoom_point
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 950:
                raise AssertionError((stage, [k.path for k in probe.targets]))
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            if zoom_point:
                io = imgui.get_io()
                io.mouse_pos, io.want_set_mouse_pos = imgui.ImVec2(*zoom_point), True
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.explorer.profiles.active:
                suffix = ("Histogram", "axes", "open")
            elif stage == 1:
                suffix = ("X", "minimum", "value")
            elif stage == 2:
                text.start("2", evidence.frames)
                stage, entered = 3, evidence.frames
            elif stage == 3:
                suffix = ("X", "maximum", "value")
            elif stage == 4:
                text.start("10", evidence.frames)
                stage, entered = 5, evidence.frames
            elif stage == 5:
                suffix = ("X", "scale", "value")
            elif stage == 6 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, True)
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, False)
                imgui.get_io().add_key_event(imgui.Key.enter, True)
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.enter, False)
                stage, entered = 9, evidence.frames
            elif stage == 9:
                close_to(measure(probe, ("axes", "x-draft")), (2, 10))
                assert measure(probe, ("axes", "scales"))[0] == 2
                suffix = ("axes", "apply", "run")
            elif stage == 10 and age > 4:
                close_to(measure(probe, ("Histogram", "x-range")), (2, 10))
                suffix = ("numeric-plot", "expand")
            elif stage == 11 and age > 4:
                close_to(measure(probe, ("Histogram", "x-range")), (2, 10))
                suffix = ("numeric-plot", "restore")
            elif stage == 12 and age > 4:
                close_to(measure(probe, ("Histogram", "x-range")), (2, 10))
                point = native.find(probe, ("Histogram", "canvas"))
                assert point
                zoom_point = point
                stage, entered = 13, evidence.frames
            elif stage == 13 and age == 5:
                imgui.get_io().add_mouse_wheel_event(0, 2)
            elif stage == 13 and age > 10:
                assert not np.allclose(
                    measure(probe, ("Histogram", "x-range")), (2, 10)
                )
                zoom_point = None
                suffix = ("numeric-plot", "fit")
            elif stage == 14 and age > 5:
                low, high = measure(probe, ("Histogram", "x-range"))
                assert low <= 1 and high >= 5, (low, high)
                file.profiles.mode = 3
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 3:
                suffix = ("Box", "axes", "open")
            elif stage == 16:
                assert native.find(probe, ("X", "minimum", "value")) is None
                assert native.find(probe, ("Y", "minimum", "value"))
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                stage, entered = 17, evidence.frames
            elif stage == 17 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                editor.choose_route("Relationships")
                stage, entered = 18, evidence.frames
            elif stage == 18 and age > 5:
                y_before = measure(probe, ("canvas", "y-range"))
                suffix = ("scatter2d", "axes", "open")
            elif stage == 19:
                suffix = ("Y", "minimum", "value")
            elif stage == 20:
                text.start("100", evidence.frames)
                stage, entered = 21, evidence.frames
            elif stage == 21:
                suffix = ("axes", "apply", "run")
            elif stage == 22 and age > 4:
                close_to(measure(probe, ("canvas", "y-range")), y_before)
                assert native.find(probe, ("Y", "minimum", "value"))
                suffix = ("Y", "minimum", "value")
            elif stage == 23:
                text.start("-2", evidence.frames)
                stage, entered = 24, evidence.frames
            elif stage == 24:
                suffix = ("Y", "maximum", "value")
            elif stage == 25:
                text.start("80", evidence.frames)
                stage, entered = 26, evidence.frames
            elif stage == 26:
                suffix = ("axes", "apply", "run")
            elif stage == 27 and age > 4:
                close_to(measure(probe, ("canvas", "y-range")), (-2, 80))
                file.plots.choose_chart(CategoryRepresentation.MEAN)
                stage, entered = 28, evidence.frames
            elif (
                stage == 28
                and age > 8
                and file.explorer.active
                and file.explorer.active.category_chart
            ):
                suffix = ("category-bars", "axes", "open")
            elif stage == 29:
                assert native.find(probe, ("Y", "minimum", "value")) is None
                suffix = ("X", "maximum", "value")
            elif stage == 30:
                text.start("100", evidence.frames)
                stage, entered = 31, evidence.frames
            elif stage == 31:
                suffix = ("axes", "apply", "run")
            elif stage == 32 and age > 4:
                assert np.isclose(measure(probe, ("category-bars", "x-range"))[1], 100)
                file.plots.choose_chart(CategoryRepresentation.BOX)
                stage, entered = 33, evidence.frames
            elif (
                stage == 33
                and age > 8
                and file.explorer.active
                and file.explorer.active.category_chart
            ):
                suffix = ("category-box", "axes", "open")
            elif stage == 34:
                assert native.find(probe, ("X", "minimum", "value")) is None
                assert native.find(probe, ("Y", "minimum", "value"))
                assert (
                    source.read_bytes() == original and not file.analysis.jobs.results
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = native.find(probe, suffix)
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_numeric_ranges_and_log_scale": True,
            "native_one_shot_ranges_allow_zoom": True,
            "native_expand_restore_preserves_axes": True,
            "native_fit_after_manual_ranges": True,
            "native_invalid_range_retains_plot_and_popup": True,
            "native_category_axes_protected": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-axes.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == "__main__":
    main()
