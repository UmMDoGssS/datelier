"""Native bootstrap for the replacement component workbench."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.application.sessions import EditorController
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.fonts import load_fonts
from datelier.gui.shell.composition import WorkbenchPage
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.playback.device import DeviceFactory, SoundDeviceOutput
from datelier.workspace.preferences import preference_path


@dataclass
class InspectionEvidence:
    """Frame counts, with timing samples retained only for verification runs."""

    frames: int = 0
    frame_intervals_ms: list[float] = field(default_factory=list)


def run_gui(
    initial_path: Path | None = None,
    *,
    smoke_frames: int = 0,
    initial_workspace: Path | None = None,
    window_size: tuple[int, int] = (1280, 800),
    preferences_path: Path | None = None,
    playback_factory: DeviceFactory = SoundDeviceOutput,
    verification: bool | None = None,
    on_probe_frame: Callable[[EditorController, GuiProbe, InspectionEvidence], None]
    | None = None,
) -> InspectionEvidence:
    """Run the workbench with idle pacing and no timing retention by default.

    Smoke/probe runs collect timings and disable idle pacing for reproducible
    measurements. Explicit verification=False lets native probes exercise normal
    pacing without saving user preferences. Background work and active playback
    keep normal sessions responsive at the active refresh rate.
    """
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    verifying = (
        bool(smoke_frames or on_probe_frame is not None)
        if verification is None
        else verification
    )
    preference_file = (
        preferences_path
        if preferences_path
        else (
            preference_path() if not smoke_frames and on_probe_frame is None else None
        )
    )
    editor, probe, evidence = (
        EditorController(preference_file, playback_factory=playback_factory),
        GuiProbe(),
        InspectionEvidence(),
    )
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
    params.fps_idling.enable_idling = not verifying
    params.callbacks.load_additional_fonts = load_fonts
    frame = FrameContext(ViewScope(""), probe)
    previous = perf_counter()
    if initial_workspace:
        editor.open_workspace(initial_workspace)
    elif initial_path:
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
        params.fps_idling.enable_idling = (
            not verifying
            and editor.workers.pending == 0
            and editor.playback.snapshot.phase
            not in (
                PlaybackPhase.STARTING,
                PlaybackPhase.PLAYING,
                PlaybackPhase.STOPPING,
            )
        )

    def draw() -> None:
        nonlocal previous
        now = perf_counter()
        if verifying and evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous) * 1000)
        previous = now
        page.render(frame)
        evidence.frames += 1
        if on_probe_frame:
            on_probe_frame(editor, probe, evidence)
        if smoke_frames and evidence.frames >= smoke_frames:
            params.app_shall_exit = True

    def safe(callback: Callable[[], None]) -> Callable[[], None]:
        def guarded() -> None:
            try:
                callback()
            except BaseException:
                page.close()
                raise

        return guarded

    params.callbacks.post_init = initialize
    params.callbacks.pre_new_frame = safe(prepare)
    params.callbacks.show_menus = safe(lambda: page.menu.render(frame.child("menus")))
    params.callbacks.show_gui = safe(draw)

    def before_exit() -> None:
        page.save_preferences()
        page.close()

    params.callbacks.before_exit = before_exit
    try:
        addons = immapp.AddOnsParams()
        addons.with_implot = True
        addons.with_implot3d = True
        immapp.run(params, addons)
    finally:
        page.close()
        editor.close()
    return evidence
