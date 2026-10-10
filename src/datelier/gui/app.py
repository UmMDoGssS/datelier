"""Native bootstrap for the replacement component workbench."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.application.editor import EditorController
from datelier.gui.components.base import FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.fonts import load_fonts
from datelier.gui.shell.page import WorkbenchPage


@dataclass
class InspectionEvidence:
    frames: int = 0
    frame_intervals_ms: list[float] = field(default_factory=list)


def run_gui(
    initial_path: Path | None = None,
    *,
    smoke_frames: int = 0,
    initial_workspace: Path | None = None,
    window_size: tuple[int, int] = (1280, 800),
    on_probe_frame: Callable[[EditorController, GuiProbe, InspectionEvidence], None]
    | None = None,
) -> InspectionEvidence:
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    if initial_workspace is not None:
        raise ValueError("Workspace restoration is not available in this rebuild stage")
    editor, probe, evidence = EditorController(), GuiProbe(), InspectionEvidence()
    page = WorkbenchPage(editor, probe)
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Datelier — data inspection"
    params.app_window_params.window_geometry.size = window_size
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    )
    params.imgui_window_params.show_menu_bar = True
    params.imgui_window_params.show_menu_view_themes = False
    params.imgui_window_params.show_menu_view = False
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.callbacks.load_additional_fonts = load_fonts
    frame = FrameContext(ViewScope(""), probe)
    previous = perf_counter()
    if initial_path:
        editor.active.open(initial_path)

    def initialize() -> None:
        imgui.get_io().config_flags |= (
            imgui.ConfigFlags_.docking_enable | imgui.ConfigFlags_.nav_enable_keyboard
        )

    def prepare() -> None:
        nonlocal frame
        probe.begin_frame()
        editor.poll()
        frame = page.prepare()

    def draw() -> None:
        nonlocal previous
        now = perf_counter()
        if evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous) * 1000)
        previous = now
        page.render(frame)
        evidence.frames += 1
        if on_probe_frame:
            on_probe_frame(editor, probe, evidence)
        if smoke_frames and evidence.frames >= smoke_frames:
            params.app_shall_exit = True

    params.callbacks.post_init = initialize
    params.callbacks.pre_new_frame = prepare
    params.callbacks.show_menus = lambda: page.menu.render(frame.child("menus"))
    params.callbacks.show_gui = draw
    params.callbacks.before_exit = page.close
    try:
        addons = immapp.AddOnsParams()
        addons.with_implot = True
        addons.with_implot3d = True
        immapp.run(params, addons)
    finally:
        editor.close()
    return evidence
