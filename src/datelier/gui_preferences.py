"""Theme/layout controls and background preference writes."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from imgui_bundle import hello_imgui, imgui

from datelier.gui_workspace_state import capture_views, restore_plots
from datelier.preferences import Preferences, Theme, read_preferences, save_preferences

if TYPE_CHECKING:
    from datelier.gui import GuiSession


class PreferenceControls:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.value, self.message = (
            read_preferences(path)
            if path is not None
            else (Preferences(), "Preferences are disabled for this smoke session.")
        )
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="preferences"
        )
        self._future: Future[None] | None = None
        self._saved_layout = self.value.layout
        self._saved_hidden = self.value.hidden_windows
        self._submitted: Preferences | None = None
        self._load_layout = True
        self._pending_layout: str | None = None
        self.reset_requested = False

    def apply_theme(self, theme: Theme | None = None) -> None:
        selected = theme if theme is not None else self.value.theme
        self.value = replace(self.value, theme=selected)
        if selected == Theme.DARK:
            imgui.style_colors_dark()
        elif selected == Theme.LIGHT:
            imgui.style_colors_light()
        else:
            imgui.style_colors_classic()

    def before_frame(self, params: hello_imgui.RunnerParams) -> None:
        if self._load_layout:
            self._load_layout = False
            if self.value.layout:
                imgui.load_ini_settings_from_memory(self.value.layout)
                params.docking_params.layout_condition = (
                    hello_imgui.DockingLayoutCondition.never
                )
            for window in params.docking_params.dockable_windows:
                window.is_visible = window.label not in self.value.hidden_windows
        if self._pending_layout is not None:
            imgui.load_ini_settings_from_memory(self._pending_layout)
            params.docking_params.layout_condition = (
                hello_imgui.DockingLayoutCondition.never
            )
            self._pending_layout = None
            for window in params.docking_params.dockable_windows:
                window.is_visible = window.label not in self._saved_hidden
        if self.reset_requested:
            imgui.internal.clear_ini_settings()
            params.docking_params.layout_condition = (
                hello_imgui.DockingLayoutCondition.first_use_ever
            )
            params.docking_params.layout_reset = True
            for window in params.docking_params.dockable_windows:
                window.is_visible = True
            self.value = replace(self.value, layout="", hidden_windows=())
            self.reset_requested = False
            self.message = "Default layout restored."

    def restore_layout(self) -> None:
        if self._saved_layout:
            self._pending_layout = self._saved_layout
        else:
            self.reset_requested = True

    def save(self, session: GuiSession, params: hello_imgui.RunnerParams) -> None:
        if self.path is None:
            return
        plots = (
            replace(session.plots.settings(), clusters=None)
            if session.loader.active
            else self.value.plots
        )
        views = capture_views(session) if session.loader.active else self.value.views
        hidden = tuple(
            w.label for w in params.docking_params.dockable_windows if not w.is_visible
        )
        self.value = Preferences(
            self.value.theme, imgui.save_ini_settings_to_memory(), plots, views, hidden
        )
        sources = (
            (session.loader.active.dataset.source.path,)
            if session.loader.active
            else ()
        )
        if self._future is not None:
            self._future.cancel()
        self._submitted = self.value
        self._future = self._executor.submit(
            save_preferences, self.path, self.value, sources=sources
        )
        self.message = "Saving preferences…"

    def poll(self) -> None:
        future = self._future
        if future is None or not future.done():
            return
        self._future = None
        try:
            future.result()
            assert self._submitted is not None
            self._saved_layout = self._submitted.layout
            self._saved_hidden = self._submitted.hidden_windows
            self.message = "Preferences saved."
        except Exception as error:
            self.message = f"Preferences failed: {error}"

    def show_menu(self, session: GuiSession, params: hello_imgui.RunnerParams) -> None:
        if not imgui.begin_menu("Preferences"):
            return
        for theme in Theme:
            if imgui.menu_item(theme.value + " theme", "", self.value.theme == theme)[
                0
            ]:
                self.apply_theme(theme)
        imgui.separator()
        if imgui.menu_item("Save preferences", "", False)[0]:
            self.save(session, params)
        if imgui.menu_item("Restore saved layout", "", False)[0]:
            self.restore_layout()
        if imgui.menu_item("Reset layout", "", False)[0]:
            self.reset_requested = True
        if imgui.menu_item("Reset plot defaults", "", False)[0]:
            from datelier.inspection.exploration import PlotSettings

            self.value = replace(self.value, plots=PlotSettings())
            if session.loader.active is not None:
                restore_plots(
                    session.plots, session.loader.active.dataset, self.value.plots
                )
                session.explorer.request(
                    session.loader.active.dataset, session.plots.settings()
                )
        imgui.separator()
        imgui.text_wrapped(self.message)
        imgui.end_menu()

    def close(self) -> None:
        self._executor.shutdown(wait=True)
        self.poll()
