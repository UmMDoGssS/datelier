"""Tabular inspection workbench; frames consume prepared state only."""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.gui.components.probe import GuiProbe
from datelier.gui.editor_controls import EditorControls
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.fonts import load_fonts
from datelier.gui.layout import configure_layout
from datelier.gui.tabs import EditorTabs
from datelier.gui.welcome import Welcome
from datelier.gui.workbench import WorkbenchPage
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.workspace.preferences import preference_path

GuiSession = FileSession


@dataclass
class InspectionEvidence:
    frames: int = 0
    loading_frames: int = 0
    failed_frames: int = 0
    first_preview_ms: float | None = None
    max_rendered_rows: int = 0
    table_dock_id: int = 0
    schema_dock_id: int = 0
    frame_intervals_ms: list[float] = field(default_factory=list)
    menu_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    dialog_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    welcome_frames: int = 0
    welcome_open_files_pixel: tuple[float, float] = (0, 0)
    welcome_open_folder_pixel: tuple[float, float] = (0, 0)
    welcome_recovery_pixel: tuple[float, float] = (0, 0)
    welcome_retry_pixel: tuple[float, float] = (0, 0)
    welcome_recent_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    comparison_frames: int = 0
    comparison_apply_pixel: tuple[float, float] = (0, 0)
    comparison_select_pixel: tuple[float, float] = (0, 0)
    comparison_settings_pixel: tuple[float, float] = (0, 0)


def run_gui(
    initial_path: Path | None = None,
    *,
    smoke_frames: int = 0,
    on_frame: Callable[[GuiSession, InspectionEvidence], None] | None = None,
    dataset_loader: DatasetLoader | None = None,
    on_editor_frame: Callable[[EditorSession, EditorTabs, InspectionEvidence], None]
    | None = None,
    initial_workspace: Path | None = None,
    preferences_path: Path | None = None,
    on_probe_frame: Callable[[EditorSession, GuiProbe, InspectionEvidence], None]
    | None = None,
) -> InspectionEvidence:
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    editor = EditorSession(
        preferences_path
        if preferences_path is not None
        else (preference_path() if not smoke_frames else None),
        initial_path=initial_path,
        initial_workspace=initial_workspace,
        loader_override=dataset_loader,
    )
    preferences = editor.preferences
    tabs = EditorTabs()
    controls = EditorControls()
    welcome = Welcome()
    evidence = InspectionEvidence()
    probe = GuiProbe()

    def guard(callback: Callable[[], None]) -> Callable[[], None]:
        def protected() -> None:
            try:
                callback()
            except BaseException:
                # Callback failures can tear the backend down without before_exit.
                # Owning GPU handles must be released while it is still alive.
                for file in editor.file_sessions:
                    file.reference_view.textures.clear()
                    file.images.canvas.clear()
                    file.audio.canvas.clear()
                raise

        return protected

    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Datelier — data inspection"
    params.app_window_params.window_geometry.size = (1280, 800)
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    page = WorkbenchPage(editor, probe, evidence, perf_counter(), welcome)
    configure_layout(
        params, {name: guard(callback) for name, callback in page.callbacks.items()}
    )
    params.callbacks.add_edge_toolbar(
        hello_imgui.EdgeToolbarType.top,
        guard(lambda: tabs.show(editor)),
        hello_imgui.EdgeToolbarOptions(size_em=2.0),
    )
    # Configure this before runner initialization: the default builder otherwise
    # replaces saved docking even when ini settings are loaded before a frame.
    if preferences.value.layout:
        params.docking_params.layout_condition = (
            hello_imgui.DockingLayoutCondition.never
        )
    params.imgui_window_params.show_menu_bar = True
    params.imgui_window_params.show_menu_view_themes = False
    params.callbacks.setup_imgui_style = preferences.apply_theme
    params.callbacks.load_additional_fonts = load_fonts

    def initialize() -> None:
        imgui.get_io().config_flags |= imgui.ConfigFlags_.nav_enable_keyboard
        preferences.before_frame(params)

    params.callbacks.post_init = initialize

    def prepare_frame() -> None:
        preferences.before_frame(params)
        page.prepare_layout(params, guard)

    params.callbacks.pre_new_frame = prepare_frame
    params.callbacks.show_menus = guard(lambda: controls.show_menu(editor, params))

    def before_exit() -> None:
        for file in editor.file_sessions:
            file.reference_view.textures.clear()
            file.images.canvas.clear()
            file.audio.canvas.clear()
        preferences.save(editor.active, params, sources=editor.source_paths)

    params.callbacks.before_exit = before_exit
    load_started = perf_counter()
    previous_frame = load_started
    if initial_workspace:
        editor.open_workspace(initial_workspace)
    elif initial_path:
        editor.active.loader.request(initial_path)

    def frame() -> None:
        nonlocal previous_frame
        now = perf_counter()
        if smoke_frames and evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous_frame) * 1000)
        previous_frame = now
        evidence.frames += 1
        editor.poll()
        if editor.pending_layout is not None:
            preferences.queue_layout(*editor.pending_layout)
            editor.pending_layout = None
        if welcome.workspace_requested:
            controls.open_dialog("Workspace actions", editor.active)
            welcome.workspace_requested = False
        controls.show_dialog(editor)
        page.show_drawer()
        evidence.menu_pixels = controls.menu_pixels.copy()
        evidence.dialog_pixels = controls.action_pixels.copy()
        paths = editor.browser.show()
        if paths is not None and editor.browser.owner is not None:
            editor.opening.request(paths, editor.browser.owner)
        session = editor.active
        if session.focus_inspect:
            session.record_views.active(session).exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            session.focus_inspect = False
        if session.focus_source:
            params.docking_params.focus_dockable_window("Source browser")
            session.focus_source = False
        if (
            session.loader.status.phase == LoadPhase.LOADING
            or editor.workspace_jobs.session_busy
        ):
            evidence.loading_frames += 1
        elif (
            session.loader.status.phase == LoadPhase.FAILED
            or editor.workspace_jobs.message.startswith("Session workspace failed:")
        ):
            evidence.failed_frames += 1
        if on_frame:
            on_frame(session, evidence)
        if on_editor_frame:
            on_editor_frame(editor, tabs, evidence)
        if on_probe_frame:
            on_probe_frame(editor, probe, evidence)
        probe.begin_frame()
        if smoke_frames and evidence.frames >= smoke_frames:
            hello_imgui.get_runner_params().app_shall_exit = True

    params.callbacks.show_gui = guard(frame)
    try:
        addons = immapp.AddOnsParams()
        addons.with_implot = True
        addons.with_implot3d = True
        immapp.run(params, addons)
    finally:
        editor.close()
        if preferences.message.startswith("Preferences failed:"):
            print(preferences.message, file=sys.stderr)
    return evidence
