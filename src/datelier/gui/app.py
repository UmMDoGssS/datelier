"""Tabular inspection workbench; frames consume prepared state only."""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from weakref import ReferenceType, ref

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.gui.arrays.browser import show_array_browser, show_deferred_records
from datelier.gui.comparisons.view import ComparisonView
from datelier.gui.data.schema import show_schema
from datelier.gui.editor_controls import EditorControls
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.fonts import load_fonts
from datelier.gui.layout import configure_layout
from datelier.gui.objects.browser import ObjectBrowser, show_view_selector
from datelier.gui.tabs import EditorTabs
from datelier.gui.text.comparison_view import TextComparisonView
from datelier.gui.welcome import Welcome
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
    comparisons = ComparisonView()
    text_comparisons = TextComparisonView()
    objects = ObjectBrowser()
    evidence = InspectionEvidence()

    def guard(callback: Callable[[], None]) -> Callable[[], None]:
        def protected() -> None:
            try:
                callback()
            except BaseException:
                # Callback failures can tear the backend down without before_exit.
                # Owning GPU handles must be released while it is still alive.
                for file in editor.file_sessions:
                    file.reference_view.textures.clear()
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

    def show_table(session: FileSession) -> None:
        show_view_selector(editor.active)
        if session.closed:
            return
        evidence.table_dock_id = imgui.get_window_dock_id()
        if show_deferred_records(editor, session.identity):
            return
        if session.loader.active is None:
            welcome.show(editor, session)
            evidence.welcome_frames += 1
            evidence.welcome_open_files_pixel = welcome.open_files_pixel
            evidence.welcome_open_folder_pixel = welcome.open_folder_pixel
            evidence.welcome_retry_pixel = welcome.retry_pixel
            evidence.welcome_recovery_pixel = welcome.recovery_pixel
            evidence.welcome_recent_pixels = {
                entry.path: pixel for entry, pixel in welcome.recent_pixels.items()
            }
            return
        if session.loader.status.message:
            imgui.text_wrapped(session.loader.status.message)
        session.table.show(
            session.loader.active,
            session.pages,
            session.selection,
            session.references,
            session.reference_view,
        )
        evidence.max_rendered_rows = max(
            evidence.max_rendered_rows, session.table.rendered_rows
        )
        if session.table.prepared_visible_rows and evidence.first_preview_ms is None:
            evidence.first_preview_ms = (perf_counter() - load_started) * 1000

    def schema(session: FileSession) -> None:
        evidence.schema_dock_id = imgui.get_window_dock_id()
        show_schema(session.loader, session.editor)

    def source_browser() -> None:
        owner = editor.active
        imported = owner.loader.active.imported if owner.loader.active else None
        if imported is not None and imported.array_catalog is not None:
            show_array_browser(editor)
        elif imported is not None and imported.checkpoint_catalog is not None:
            owner.checkpoint_view.show(owner)
            if not imported.checkpoint_catalog.tensors or imgui.collapsing_header(
                "Checkpoint hierarchy"
            ):
                objects.show(owner)
        else:
            objects.show(owner)

    def compare_files() -> None:
        if imgui.begin_tab_bar("File comparison types"):
            if imgui.begin_tab_item("Columns")[0]:
                comparisons.show(editor)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Text corpora")[0]:
                text_comparisons.show(editor)
                imgui.end_tab_item()
            imgui.end_tab_bar()
        evidence.comparison_frames = comparisons.plot_frames
        evidence.comparison_apply_pixel = comparisons.controls.apply_pixel
        evidence.comparison_select_pixel = comparisons.select_pixel
        evidence.comparison_settings_pixel = comparisons.settings_pixel

    def explore(session: FileSession) -> None:
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

    def bind(callback: Callable[[FileSession], None]) -> Callable[[], None]:
        previous: ReferenceType[FileSession] | None = None

        def show() -> None:
            nonlocal previous
            session = editor.active.record_views.active(editor.active)
            panel = imgui.internal.get_current_window().name
            switching = previous is None or previous() is not session
            if switching:
                x, y = session.panel_scroll.get(panel, (0, 0))
                imgui.set_scroll_x(x)
                imgui.set_scroll_y(y)
                previous = ref(session)
            imgui.push_id(session.identity)
            try:
                callback(session)
            finally:
                imgui.pop_id()
            if not switching:
                session.panel_scroll[panel] = (
                    imgui.get_scroll_x(),
                    imgui.get_scroll_y(),
                )

        return guard(show)

    configure_layout(
        params,
        {
            "Source browser": guard(source_browser),
            "Explore": bind(explore),
            "Compare files": guard(compare_files),
            "Text": bind(lambda session: session.text.show(session)),
            "Inspect": bind(
                lambda session: session.inspect.show(
                    session.references,
                    session.reference_view,
                    session.selection,
                    session.table,
                    session,
                )
            ),
            "Table preview": bind(show_table),
            "Schema and nulls": bind(schema),
            "Analysis": bind(
                lambda session: session.analysis.show_panel(
                    session.loader.active.dataset if session.loader.active else None,
                    session.plots,
                )
            ),
            "Transform and history": bind(
                lambda session: session.operations.show(
                    session.editor,
                    loading=session.loader.status.phase == LoadPhase.LOADING
                    or session.exporter.busy
                    or session.workspace.jobs.busy
                    or editor.workspace_jobs.session_busy
                    or editor.workspace_jobs.recovering(session.identity),
                )
            ),
            "Export table": bind(
                lambda session: session.exports.show(
                    session.editor,
                    session.exporter,
                    loading=session.loader.status.phase == LoadPhase.LOADING
                    or session.workspace.jobs.busy
                    or editor.workspace_jobs.session_busy
                    or editor.workspace_jobs.recovering(session.identity),
                )
            ),
        },
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
    params.callbacks.post_init = lambda: preferences.before_frame(params)
    params.callbacks.pre_new_frame = lambda: preferences.before_frame(params)
    params.callbacks.show_menus = guard(lambda: controls.show_menu(editor, params))

    def before_exit() -> None:
        for file in editor.file_sessions:
            file.reference_view.textures.clear()
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
        evidence.menu_pixels = controls.menu_pixels.copy()
        evidence.dialog_pixels = controls.action_pixels.copy()
        paths = editor.browser.show()
        if paths is not None and editor.browser.owner is not None:
            editor.opening.request(paths, editor.browser.owner)
        session = editor.active
        if session.focus_inspect:
            params.docking_params.focus_dockable_window("Inspect")
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
