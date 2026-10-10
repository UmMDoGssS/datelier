"""Workbench page composing four dockable panels and contextual tab families."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING
from weakref import ReferenceType, ref

from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.gui.arrays.browser import show_array_browser, show_deferred_records
from datelier.gui.comparisons.tabs import ColumnComparisonTab, ComparisonTabs
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.layout import configure_layout
from datelier.gui.objects.browser import ObjectBrowser, show_view_selector
from datelier.gui.welcome import Welcome
from datelier.io.loading import LoadPhase

if TYPE_CHECKING:
    from datelier.gui.app import InspectionEvidence


class SessionPanel(Component, ABC):
    """Panel-level file binding preserves independent scroll state on tab changes."""

    def __init__(
        self,
        current: Callable[[], FileSession],
        probe: GuiProbe,
        owner_id: Callable[[], str],
    ) -> None:
        self.current, self.probe, self.owner_id = current, probe, owner_id
        self.previous: ReferenceType[FileSession] | None = None
        self.dock_id = 0

    def render(self, frame: FrameContext) -> None:
        session = self.current()
        self.dock_id = imgui.get_window_dock_id()
        panel = imgui.internal.get_current_window().name
        switching = self.previous is None or self.previous() is not session
        if switching:
            x, y = session.panel_scroll.get(panel, (0, 0))
            imgui.set_scroll_x(x)
            imgui.set_scroll_y(y)
            self.previous = ref(session)
        imgui.push_id(session.identity)
        self.show(
            session,
            FrameContext(
                ViewScope(self.owner_id(), session.identity, session.loader.revision),
                self.probe,
            ),
        )
        imgui.pop_id()
        if not switching:
            session.panel_scroll[panel] = (imgui.get_scroll_x(), imgui.get_scroll_y())

    @abstractmethod
    def show(self, session: FileSession, frame: FrameContext) -> None: ...


class SourcePanel(SessionPanel):
    def __init__(
        self, editor: EditorSession, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        super().__init__(
            lambda: editor.active.record_views.active(editor.active),
            probe,
            lambda: editor.active.identity,
        )
        self.editor, self.evidence = editor, evidence
        self.objects = ObjectBrowser()
        self.observed_source: object = None

    def show(self, session: FileSession, frame: FrameContext) -> None:
        owner = self.editor.active
        active = owner.loader.active
        imported = active.imported if active else None
        structured = imported is not None and (
            imported.object_root is not None
            or imported.array_catalog is not None
            or imported.checkpoint_catalog is not None
        )
        requested = "Source" if structured else "Columns"
        selecting = active is not self.observed_source
        self.observed_source = active
        if imgui.begin_tab_bar("Source and columns"):
            if imgui.begin_tab_item(
                "Columns",
                flags=imgui.TabItemFlags_.set_selected
                if selecting and requested == "Columns"
                else 0,
            )[0]:
                self.evidence.schema_dock_id = imgui.get_window_dock_id()
                session.schema_panel.render(frame)
                imgui.end_tab_item()
            if imgui.begin_tab_item(
                "Source",
                flags=imgui.TabItemFlags_.set_selected
                if selecting and requested == "Source"
                else 0,
            )[0]:
                if imported is not None and imported.array_catalog is not None:
                    show_array_browser(self.editor)
                elif imported is not None and imported.checkpoint_catalog is not None:
                    owner.checkpoint_view.show(owner)
                    if (
                        not imported.checkpoint_catalog.tensors
                        or imgui.collapsing_header("Checkpoint hierarchy")
                    ):
                        self.objects.show(owner)
                else:
                    self.objects.show(owner)
                imgui.end_tab_item()
            imgui.end_tab_bar()


class CanvasPanel(SessionPanel):
    def __init__(
        self,
        editor: EditorSession,
        probe: GuiProbe,
        welcome: Welcome,
        evidence: InspectionEvidence,
    ) -> None:
        super().__init__(
            lambda: editor.active.record_views.active(editor.active),
            probe,
            lambda: editor.active.identity,
        )
        self.editor, self.welcome, self.evidence = editor, welcome, evidence
        self.comparisons = ComparisonTabs()

    def show(self, session: FileSession, frame: FrameContext) -> None:
        if session.loader.active is None:
            self.welcome.show(self.editor, session)
            self.evidence.welcome_frames += 1
            self.evidence.welcome_open_files_pixel = self.welcome.open_files_pixel
            self.evidence.welcome_open_folder_pixel = self.welcome.open_folder_pixel
            self.evidence.welcome_retry_pixel = self.welcome.retry_pixel
            self.evidence.welcome_recovery_pixel = self.welcome.recovery_pixel
            self.evidence.welcome_recent_pixels = {
                entry.path: pixel for entry, pixel in self.welcome.recent_pixels.items()
            }
            return
        view = session.exploration
        if view.tab:
            self.editor.navigation.comparing = False
        view.contextual = True
        view.comparison = self.comparisons
        view.comparing = self.editor.navigation.comparing
        view.choose_canvas = self.editor.navigation.choose_canvas
        self.comparisons.bind_view(self.editor)
        view.show(
            session.explorer,
            session.selection,
            session.table,
            session.plots,
            session.loader.active.dataset,
            session.analysis,
            session,
        )
        columns = self.comparisons.tabs[0]
        assert isinstance(columns, ColumnComparisonTab)
        self.evidence.comparison_frames = columns.view.plot_frames
        self.evidence.comparison_apply_pixel = columns.view.controls.apply_pixel
        self.evidence.comparison_select_pixel = columns.view.select_pixel
        self.evidence.comparison_settings_pixel = columns.view.settings_pixel


class ContextTab(Component, ABC):
    label: str

    def __init__(
        self, current: Callable[[], FileSession], editor: EditorSession
    ) -> None:
        self.current, self.editor = current, editor


class ViewContext(ContextTab):
    label = "View"

    def render(self, frame: FrameContext) -> None:
        session = self.current()
        active = session.loader.active
        if self.editor.navigation.comparing:
            imgui.text_wrapped(
                "Comparison mappings and scope are in the selected comparison view."
            )
            return
        if active is None:
            return
        dataset, view = active.dataset, session.exploration
        pending = session.analysis.pending_result
        if pending is not None:
            imgui.text_wrapped(f"{pending} result ready")
            opened = imgui.button("Open result")
            low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            frame.record("open-result", ((low.x + high.x) / 2, (low.y + high.y) / 2))
            if opened:
                session.analysis.panel_source = pending
                if pending.is_clustering:
                    session.plots.choose_color(pending.value)
                else:
                    session.analysis.source = pending
                session.plots.relationship_chart = "Scatter"
                view.tab = "Relationships"
                session.analysis.pending_result = None
        renderers: dict[str, Callable[[], None]] = {
            "Profiles": lambda: view.profile.show_controls(dataset),
            "Relationships": lambda: self.relationships(session),
            "Correlations": lambda: self.correlations(session),
            "Inspect": session.inspect.controls.show,
        }
        renderers[view.active_tab]()
        session.plots.show(session.explorer, dataset)

    def relationships(self, session: FileSession) -> None:
        assert session.loader.active is not None
        dataset = session.loader.active.dataset
        if session.exploration.categories.controls(
            session.plots, session.explorer, dataset
        ):
            return
        session.analysis.scatter_controls(
            dataset, session.plots, session.explorer, setup=False
        )
        algorithms = list(Algorithm)
        current = session.analysis.selected_algorithm(session.plots)
        changed, selected = imgui.combo(
            "Method settings", algorithms.index(current), [str(a) for a in algorithms]
        )
        if changed:
            session.analysis.panel_source = algorithms[selected]
        session.analysis.show_panel(dataset, session.plots)

    def correlations(self, session: FileSession) -> None:
        assert session.loader.active is not None
        plots, explorer, dataset = (
            session.plots,
            session.explorer,
            session.loader.active.dataset,
        )
        view = session.exploration.relationships
        view.show_features(plots, explorer, dataset)
        view.controls(
            len(
                plots.relationship_features
                or plots.numeric[: plots.correlation_columns]
            ),
            plots,
            explorer,
            dataset,
        )


class TransformContext(ContextTab):
    label = "Transform"

    def render(self, frame: FrameContext) -> None:
        session = self.current()
        session.operations.show(
            session.editor,
            loading=session.loader.status.phase == LoadPhase.LOADING
            or session.exporter.busy
            or session.workspace.jobs.busy
            or self.editor.workspace_jobs.session_busy
            or self.editor.workspace_jobs.recovering(session.identity),
            history=False,
        )


class HistoryContext(ContextTab):
    label = "History"

    def render(self, frame: FrameContext) -> None:
        self.current().operations.show_history(self.current().editor)


class ContextPanel(SessionPanel):
    def __init__(self, editor: EditorSession, probe: GuiProbe) -> None:
        def current() -> FileSession:
            return editor.active.record_views.active(editor.active)

        super().__init__(current, probe, lambda: editor.active.identity)
        self.editor = editor
        self.tabs: tuple[ContextTab, ...] = (
            ViewContext(current, editor),
            TransformContext(current, editor),
            HistoryContext(current, editor),
        )

    def show(self, session: FileSession, frame: FrameContext) -> None:
        if imgui.begin_tab_bar("Context tabs"):
            for tab in self.tabs:
                if imgui.begin_tab_item(tab.label)[0]:
                    self.editor.navigation.context_tab = tab.label
                    if self.editor.navigation.comparing and tab.label != "View":
                        imgui.text_wrapped(
                            "Choose a file inspection view to transform "
                            "or view its history."
                        )
                    else:
                        tab.render(frame.child(tab.label))
                    imgui.end_tab_item()
            imgui.end_tab_bar()


class TablePanel(SessionPanel):
    def __init__(
        self,
        editor: EditorSession,
        probe: GuiProbe,
        evidence: InspectionEvidence,
        started: float,
    ) -> None:
        super().__init__(
            lambda: editor.active.record_views.active(editor.active),
            probe,
            lambda: editor.active.identity,
        )
        self.editor, self.evidence, self.started = editor, evidence, started

    def show(self, session: FileSession, frame: FrameContext) -> None:
        show_view_selector(self.editor.active)
        if session.closed or show_deferred_records(self.editor, session.identity):
            return
        self.evidence.table_dock_id = imgui.get_window_dock_id()
        if session.loader.active is None:
            imgui.text_wrapped("Open a source to preview its records.")
            return
        session.table.show(
            session.loader.active,
            session.pages,
            session.selection,
            session.references,
            session.reference_view,
        )
        self.evidence.max_rendered_rows = max(
            self.evidence.max_rendered_rows, session.table.rendered_rows
        )
        if (
            session.table.prepared_visible_rows
            and self.evidence.first_preview_ms is None
        ):
            self.evidence.first_preview_ms = (perf_counter() - self.started) * 1000


@dataclass
class WorkbenchPage(Container):
    editor: EditorSession
    probe: GuiProbe
    evidence: InspectionEvidence
    started: float
    welcome: Welcome
    compact: bool = False
    _dock_signature: tuple[int, ...] = ()
    _settling_frames: int = 10

    def __post_init__(self) -> None:
        self.panels: dict[str, SessionPanel] = {
            "Source browser": SourcePanel(self.editor, self.probe, self.evidence),
            "Explore": CanvasPanel(
                self.editor, self.probe, self.welcome, self.evidence
            ),
            "Context": ContextPanel(self.editor, self.probe),
            "Table preview": TablePanel(
                self.editor, self.probe, self.evidence, self.started
            ),
        }

    @property
    def children(self) -> tuple[Component, ...]:
        return tuple(self.panels.values())

    @property
    def callbacks(self) -> dict[str, Callable[[], None]]:
        frame = FrameContext(ViewScope(""), self.probe)
        return {
            name: lambda panel=panel: panel.render(frame)
            for name, panel in self.panels.items()
        }

    def prepare_layout(
        self,
        params: hello_imgui.RunnerParams,
        guard: Callable[[Callable[[], None]], Callable[[], None]],
    ) -> None:
        signature = tuple(panel.dock_id for panel in self.panels.values())
        if self._settling_frames:
            self._settling_frames -= 1
        elif self._dock_signature and signature != self._dock_signature:
            self.editor.preferences.layout_customized = True
        if any(signature):
            self._dock_signature = signature
        if self.editor.preferences.layout_customized:
            return
        compact = imgui.get_io().display_size.x < 1100
        if compact == self.compact:
            return
        self.compact = compact
        self._settling_frames = 10
        configure_layout(
            params,
            {name: guard(callback) for name, callback in self.callbacks.items()},
            compact=compact,
        )
        params.docking_params.layout_reset = True

    def show_drawer(self) -> None:
        if not self.compact or not self.editor.navigation.context_open:
            return
        viewport = imgui.get_main_viewport()
        imgui.set_next_window_pos(
            (
                viewport.work_pos.x + viewport.work_size.x - 290,
                viewport.work_pos.y + 40,
            ),
            imgui.Cond_.always,
        )
        imgui.set_next_window_size((280, viewport.work_size.y - 50), imgui.Cond_.always)
        visible, opened = imgui.begin("Context drawer", True)
        self.editor.navigation.context_open = bool(opened)
        if visible:
            self.panels["Context"].render(FrameContext(ViewScope(""), self.probe))
        imgui.end()
