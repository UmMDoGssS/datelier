"""Tabular inspection workbench; frames consume prepared state only."""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.core.jobs import SharedWorkers
from datelier.gui.data.import_controls import show_schema
from datelier.gui.file_session import FileSession
from datelier.gui.layout import configure_layout
from datelier.gui.workspace.preferences import PreferenceControls
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


def run_gui(
    initial_path: Path | None = None,
    *,
    smoke_frames: int = 0,
    on_frame: Callable[[GuiSession, InspectionEvidence], None] | None = None,
    dataset_loader: DatasetLoader | None = None,
    initial_workspace: Path | None = None,
    preferences_path: Path | None = None,
) -> InspectionEvidence:
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    workers = SharedWorkers()
    preferences = PreferenceControls(
        preferences_path
        if preferences_path is not None
        else (preference_path() if not smoke_frames else None),
        executor=workers,
    )
    session = FileSession.create(
        preferences,
        executor=workers,
        source_path=initial_path,
        workspace_path=initial_workspace,
        loader_override=dataset_loader,
    )
    evidence = InspectionEvidence()
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Datelier — data inspection"
    params.app_window_params.window_geometry.size = (1280, 800)
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    def show_table() -> None:
        evidence.table_dock_id = imgui.get_window_dock_id()
        session.table.show(session.loader.active, session.pages, session.selection)
        evidence.max_rendered_rows = max(
            evidence.max_rendered_rows, session.table.rendered_rows
        )
        if session.table.prepared_visible_rows and evidence.first_preview_ms is None:
            evidence.first_preview_ms = (perf_counter() - load_started) * 1000

    def schema() -> None:
        evidence.schema_dock_id = imgui.get_window_dock_id()
        show_schema(session.loader, session.editor)

    def explore() -> None:
        session.plots.show(
            session.explorer,
            session.loader.active.dataset if session.loader.active else None,
        )
        session.exploration.show(
            session.explorer,
            session.selection,
            session.table,
            session.plots,
            session.loader.active.dataset if session.loader.active else None,
            session.analysis,
        )

    configure_layout(
        params,
        {
            "Explore": explore,
            "Open dataset": lambda: session.controls.show(session.loader),
            "Workspace": lambda: session.workspace.show(session),
            "Table preview": show_table,
            "Schema and nulls": schema,
            "Analysis": lambda: session.analysis.show_panel(
                session.loader.active.dataset if session.loader.active else None,
                session.plots,
            ),
            "Transform and history": lambda: session.operations.show(
                session.editor,
                loading=session.loader.status.phase == LoadPhase.LOADING
                or session.exporter.busy
                or session.workspace.jobs.busy,
            ),
            "Export table": lambda: session.exports.show(
                session.editor,
                session.exporter,
                loading=session.loader.status.phase == LoadPhase.LOADING
                or session.workspace.jobs.busy,
            ),
        },
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
    params.callbacks.post_init = lambda: preferences.before_frame(params)
    params.callbacks.pre_new_frame = lambda: preferences.before_frame(params)
    params.callbacks.show_menus = lambda: preferences.show_menu(session, params)
    params.callbacks.before_exit = lambda: preferences.save(session, params)
    load_started = perf_counter()
    previous_frame = load_started
    if initial_workspace:
        session.workspace.open(session)
    elif initial_path:
        session.loader.request(initial_path)

    def frame() -> None:
        nonlocal previous_frame
        now = perf_counter()
        if smoke_frames and evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous_frame) * 1000)
        previous_frame = now
        evidence.frames += 1
        session.poll()
        preferences.poll()
        if session.loader.status.phase == LoadPhase.LOADING:
            evidence.loading_frames += 1
        elif session.loader.status.phase == LoadPhase.FAILED:
            evidence.failed_frames += 1
        if on_frame:
            on_frame(session, evidence)
        if smoke_frames and evidence.frames >= smoke_frames:
            hello_imgui.get_runner_params().app_shall_exit = True

    params.callbacks.show_gui = frame
    try:
        addons = immapp.AddOnsParams()
        addons.with_implot = True
        addons.with_implot3d = True
        immapp.run(params, addons)
    finally:
        session.close()
        preferences.close()
        workers.shutdown(wait=True)
        if preferences.message.startswith("Preferences failed:"):
            print(preferences.message, file=sys.stderr)
    return evidence
