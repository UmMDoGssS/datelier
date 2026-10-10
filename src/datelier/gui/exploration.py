"""Docked exploration dashboard; renders bounded, prepared values."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.core.dataset import Dataset
from datelier.gui.analysis.session import AnalysisSession
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.data.table import TableView
from datelier.gui.explore_tabs import (
    CorrelationsTab,
    ExplorationBinding,
    ExploreTab,
    InspectTab,
    ProfilesTab,
    RelationshipsTab,
)
from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.categories import CategoryView
from datelier.gui.plots.controls import PlotControls
from datelier.gui.plots.relationships import RelationshipView
from datelier.gui.plots.scatter import ScatterView
from datelier.gui.plots.scatter3d import Scatter3DView
from datelier.gui.plots.selection import ScatterInteraction
from datelier.gui.profiles.view import ProfileView
from datelier.inspection.exploration import Dashboard, Explorer
from datelier.plotting.selection import LinkedSelection

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


@dataclass
class ExplorationView(BoundView[ExplorationBinding]):
    profile: ProfileView = field(default_factory=ProfileView)
    comparison_area: PlotArea = field(default_factory=PlotArea)
    scatter: ScatterView = field(default_factory=ScatterView)
    comparison_mode: int = 0
    relationships: RelationshipView = field(default_factory=RelationshipView)
    scatter_index: int = 0
    plot_frames: int = 0
    scatter_frames: int = 0
    dock_id: int = 0
    tab: str = "Profiles"
    active_tab: str = "Profiles"
    saved_scatter_index: int | None = None
    _dashboard: Dashboard | None = None
    categories: CategoryView = field(default_factory=CategoryView)

    tabs: tuple[ExploreTab, ...] = field(init=False)

    def __post_init__(self) -> None:
        self.tabs = (
            ProfilesTab(self),
            RelationshipsTab(self),
            CorrelationsTab(self),
            InspectTab(self),
        )

    @property
    def scatter_area(self) -> PlotArea:
        return self.scatter.area

    @property
    def scatter3d_area(self) -> PlotArea:
        return self.scatter.area3d

    @property
    def scatter3d(self) -> Scatter3DView:
        return self.scatter.scatter3d

    @property
    def interaction(self) -> ScatterInteraction:
        return self.scatter.interaction

    @property
    def fit(self) -> bool:
        return self.scatter.fit

    @fit.setter
    def fit(self, value: bool) -> None:
        self.scatter.fit = value

    @property
    def profile_index(self) -> int:
        return self.profile.index

    @profile_index.setter
    def profile_index(self, value: int) -> None:
        if value != self.profile.index:
            self.profile.selection.columns = None
        self.profile.index = value

    @property
    def profile_mode(self) -> int:
        return self.profile.mode

    @profile_mode.setter
    def profile_mode(self, value: int) -> None:
        self.profile.mode = value

    def show(
        self,
        explorer: Explorer,
        selection: LinkedSelection,
        table: TableView,
        plots: PlotControls | None = None,
        dataset: Dataset | None = None,
        analysis: AnalysisSession | None = None,
        owner: FileSession | None = None,
    ) -> None:
        self.bind_view(
            ExplorationBinding(
                explorer, selection, table, plots, dataset, analysis, owner
            )
        )
        self.render(
            FrameContext(ViewScope(owner.identity if owner else ""), GuiProbe())
        )

    def draw(self, binding: ExplorationBinding, frame: FrameContext) -> None:
        self.dock_id = imgui.get_window_dock_id()
        dashboard = binding.explorer.active
        if dashboard is not None:
            profiles = dashboard.profiles
            imgui.text(
                f"{profiles.row_count:,} rows · {profiles.total_columns} columns"
            )
        requested_tab, self.tab = self.tab, ""
        if requested_tab == "Scatter":
            requested_tab = "Relationships"
        if imgui.begin_tab_bar("Exploration views"):
            for tab in self.tabs:
                flags = (
                    imgui.TabItemFlags_.set_selected
                    if requested_tab == tab.label
                    else 0
                )
                if imgui.begin_tab_item(tab.label, flags=flags)[0]:
                    self.active_tab = tab.label
                    tab.bind_view(binding)
                    tab.render(frame.child(tab.label))
                    imgui.end_tab_item()
            imgui.end_tab_bar()
