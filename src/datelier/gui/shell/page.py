"""Explicit assembly is the only GUI layer that knows application controllers."""

from dataclasses import replace
from pathlib import Path

from imgui_bundle import hello_imgui, imgui

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_views
from datelier.gui.comparisons.assembly import assemble_comparisons
from datelier.gui.components.actions import JobSnapshot
from datelier.gui.components.base import FrameContext, Group, Page
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.shell.assembly import FileComponents, assemble_file
from datelier.gui.shell.browser import FileBrowserDialog
from datelier.gui.shell.docking import DockHost, DockPanel
from datelier.gui.shell.export import ExportDialog, ExportPort
from datelier.gui.shell.menu import Menu, MenuAction, MenuBar, RecentMenu
from datelier.gui.shell.navigation import FileTab, FileTabs
from datelier.gui.shell.status import WorkbenchNotice
from datelier.gui.shell.workspace import WorkspaceDialog
from datelier.io.exporting import ExportFormat
from datelier.pipeline.editing import HistoryAction
from datelier.workspace.preferences import Theme


class WorkbenchPage(Page):
    def __init__(self, editor: EditorController, probe: GuiProbe) -> None:
        self.editor, self.probe = editor, probe
        self.files: dict[str, FileComponents] = {}
        self.compare = assemble_comparisons(editor.compare)
        empty = Group("empty", ())
        self.host = DockHost(
            DockPanel("source", "Source browser", empty),
            DockPanel("canvas", "Explore", empty),
            DockPanel("context", "Context", empty),
            DockPanel("table", "Table preview", empty),
        )
        self.open_dialog = FileBrowserDialog(editor.browser, editor.open_paths)

        def capture_export() -> ExportPort | None:
            file = editor.current
            active = file.inspection
            if active is None:
                return None

            def request(path: Path, format: ExportFormat, overwrite: bool) -> None:
                file.exporter.request(
                    active.dataset,
                    path,
                    format,
                    overwrite=overwrite,
                    sources=tuple(
                        source
                        for f in editor.all_files
                        for source in (
                            f.loader.status.path,
                            f.inspection.dataset.source.path if f.inspection else None,
                        )
                        if source is not None
                    ),
                )
                editor.watch_export(file.exporter)

            return ExportPort(
                active.dataset.source.path.name
                + (f" · {file.view_name}" if file.view_name else ""),
                request,
                lambda: JobSnapshot(file.exporter.message, file.exporter.busy),
            )

        self.export_dialog = ExportDialog(capture_export)
        self.workspace_dialog = WorkspaceDialog(
            self.save_workspace,
            editor.open_workspace,
            lambda: JobSnapshot(editor.workspace.message, editor.workspace.busy),
            editor.workspace.abandon,
        )
        self.menu = MenuBar(
            (
                Menu(
                    "File",
                    (
                        MenuAction(
                            "open",
                            "Open files or folder…",
                            lambda: setattr(self.open_dialog, "requested", True),
                            shortcut="Ctrl+O",
                        ),
                        MenuAction(
                            "workspace",
                            "Session workspace…",
                            lambda: setattr(self.workspace_dialog, "requested", True),
                        ),
                        MenuAction(
                            "export",
                            "Export active source…",
                            lambda: setattr(self.export_dialog, "requested", True),
                        ),
                        RecentMenu(
                            lambda: editor.preferences.value.recent, editor.open_recent
                        ),
                        MenuAction(
                            "quit",
                            "Quit",
                            lambda: setattr(
                                hello_imgui.get_runner_params(), "app_shall_exit", True
                            ),
                        ),
                    ),
                ),
                Menu(
                    "View",
                    (
                        MenuAction(
                            "reset",
                            "Reset layout",
                            lambda: setattr(self.host, "reset", True),
                        ),
                        MenuAction(
                            "context",
                            "Context",
                            self.host.toggle_context,
                            lambda: self.host.context.visible,
                        ),
                        MenuAction(
                            "table",
                            "Table",
                            self.host.toggle_table,
                            lambda: self.host.table.visible,
                        ),
                    ),
                ),
                Menu(
                    "Theme",
                    tuple(
                        MenuAction(
                            theme.value,
                            theme.value,
                            lambda theme=theme: self.choose_theme(theme),
                            lambda theme=theme: editor.preferences.value.theme == theme,
                        )
                        for theme in Theme
                    ),
                ),
            )
        )
        self._preference_revision = -1
        self._theme: Theme | None = None
        tabs = FileTabs(
            lambda: tuple(
                FileTab(f.identity, f.title, f.identity == editor.active_id)
                for f in editor.files
            ),
            editor.activate,
            editor.close_file,
            editor.new_file,
            lambda: self._history(HistoryAction.UNDO),
            lambda: self._history(HistoryAction.REDO),
            self.host.toggle_context,
            self.host.toggle_table,
        )
        super().__init__(
            "page",
            (
                tabs,
                WorkbenchNotice(
                    lambda: editor.notice, lambda: setattr(editor, "notice", "")
                ),
                self.host,
                self.open_dialog,
                self.export_dialog,
                self.workspace_dialog,
            ),
        )

    def choose_theme(self, theme: Theme) -> None:
        self.editor.preferences.value = replace(
            self.editor.preferences.value, theme=theme
        )

    def layout(self) -> str:
        return (
            imgui.save_ini_settings_to_memory()
            + "\n[Datelier][Workbench]\nNativeTree=1\n"
        )

    def hidden(self) -> tuple[str, ...]:
        return tuple(
            panel.label
            for panel in self.host.children
            if isinstance(panel, DockPanel) and not panel.visible
        )

    def save_workspace(self, path: Path, overwrite: bool) -> None:
        self.editor.save_workspace(
            path, self.layout(), self.hidden(), self.host.customized, overwrite
        )

    def save_preferences(self) -> None:
        file = self.editor.current
        value = replace(
            self.editor.preferences.value,
            layout=self.layout(),
            hidden_windows=self.hidden(),
            custom_layout=self.host.customized,
            plots=replace(file.plots.settings(), clusters=None),
            views=capture_views(file),
        )
        sources = tuple(
            file.inspection.dataset.source.path
            for file in self.editor.all_files
            if file.inspection
        )
        self.editor.preferences.save(value, sources)

    def _history(self, action: HistoryAction) -> None:
        if (
            not self.editor.navigation.comparing
            and self.editor.current.editor.pipeline
            and not self.editor.current.editor.busy
        ):
            self.editor.current.editor.request(action)

    def prepare(self) -> FrameContext:
        preferences = self.editor.preferences
        if preferences.ready and preferences.changed != self._preference_revision:
            self._preference_revision = preferences.changed
            self._load_layout(
                preferences.value.layout,
                preferences.value.hidden_windows,
                preferences.value.custom_layout,
            )
            if "layout updated" in preferences.message:
                self.editor.notice = preferences.message
        if self.editor.pending_layout is not None:
            self._load_layout(*self.editor.pending_layout)
            self.editor.pending_layout = None
        theme = preferences.value.theme
        if self._theme != theme:
            {
                Theme.DARK: imgui.style_colors_dark,
                Theme.LIGHT: imgui.style_colors_light,
                Theme.CLASSIC: imgui.style_colors_classic,
            }[theme]()
            self._theme = theme
        known = {f.identity for f in self.editor.all_files}
        for identity in set(self.files) - known:
            self.files.pop(identity).close()
        for file in self.editor.all_files:
            if file.identity not in self.files:
                self.files[file.identity] = assemble_file(
                    file, self.editor, self.compare
                )
        file = self.editor.current
        components = self.files[file.identity]
        for panel, content in (
            (
                self.host.source,
                Group(
                    "source-region",
                    (self.files[self.editor.active_id].source, components.columns),
                ),
            ),
            (self.host.canvas, components.canvas),
            (self.host.context, components.context),
            (self.host.table, components.table),
        ):
            panel.children = (content,)
        return FrameContext(
            ViewScope(
                self.editor.active_id,
                file.identity if file is not self.editor.active else "",
                file.loader.revision,
            ),
            self.probe,
        )

    def _load_layout(
        self, layout: str, hidden: tuple[str, ...], customized: bool
    ) -> None:
        if layout and "[Datelier][Workbench]" in layout:
            imgui.load_ini_settings_from_memory(layout)
            self.host.initialized = True
            self.host.customized = customized
            self.host.compact = (
                imgui.get_main_viewport().work_size.x < 1100 and not customized
            )
        elif layout:
            self.editor.notice = (
                "Workbench layout updated; saved recipes and settings preserved."
            )
            hidden = ()
        for panel in self.host.children:
            if isinstance(panel, DockPanel):
                panel.visible = panel.label not in hidden

    def close(self) -> None:
        for components in self.files.values():
            components.close()
        self.files.clear()
        self.compare.close()
        self.export_dialog.close()
