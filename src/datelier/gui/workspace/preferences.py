"""Theme/layout controls and background preference writes."""

from concurrent.futures import Executor, Future
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from imgui_bundle import hello_imgui, imgui

from datelier.core.jobs import JobExecutor
from datelier.gui.workspace.state import capture_views, restore_plots
from datelier.workspace.preferences import (
    Preferences,
    Theme,
    read_preferences,
    save_preferences,
)
from datelier.workspace.recent import RecentSource, remember

if TYPE_CHECKING:
    from datelier.gui.app import GuiSession


class PreferenceControls:
    def __init__(self, path: Path | None, *, executor: Executor | None = None) -> None:
        self.path = path
        self.value, self.message = (
            read_preferences(path)
            if path is not None
            else (Preferences(), "Preferences are disabled for this smoke session.")
        )
        self._executor = JobExecutor(executor, max_workers=1, name="preferences")
        self._future: Future[None] | None = None
        self._saved_layout = self.value.layout
        self._saved_hidden = self.value.hidden_windows
        self._submitted: Preferences | None = None
        self._load_layout = True
        self._pending_layout: str | None = None
        self.reset_requested = False
        self.menu_pixels: dict[str, tuple[float, float]] = {}

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

    def remember(self, source: RecentSource) -> None:
        self.value = replace(self.value, recent=remember(self.value.recent, source))

    def save(
        self,
        session: GuiSession,
        params: hello_imgui.RunnerParams,
        *,
        sources: tuple[Path, ...] = (),
    ) -> None:
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
        self.value = replace(
            self.value,
            layout=imgui.save_ini_settings_to_memory(),
            plots=plots,
            views=views,
            hidden_windows=hidden,
        )
        sources = sources or (
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

    def show_menu(
        self,
        session: GuiSession,
        params: hello_imgui.RunnerParams,
        *,
        sources: tuple[Path, ...] = (),
    ) -> None:
        def pixel(label: str) -> None:
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            self.menu_pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

        def item(label: str, selected: bool = False) -> bool:
            clicked = imgui.menu_item(label, "", selected)[0]
            pixel(label)
            return clicked

        opened = imgui.begin_menu("Preferences")
        pixel("Preferences")
        if not opened:
            return
        for theme in Theme:
            if item(theme.value + " theme", self.value.theme == theme):
                self.apply_theme(theme)
        imgui.separator()
        if item("Save preferences"):
            self.save(session, params, sources=sources)
        if item("Restore saved layout"):
            self.restore_layout()
        if item("Reset layout"):
            self.reset_requested = True
        if item("Reset plot defaults"):
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
