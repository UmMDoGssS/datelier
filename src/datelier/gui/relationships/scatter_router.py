"""2D and 3D scatter renderers retain independent native interaction state."""

from collections.abc import Callable

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.relationships.scatter import ScatterPlot
from datelier.gui.relationships.scatter3d import Scatter3DPlot
from datelier.plotting.data import Scatter
from datelier.plotting.selection import LinkedSelection


class ScatterRouter(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        dimensions: Callable[[], int],
    ) -> None:
        super().__init__("scatter-router")
        self.dimensions = dimensions
        self.routes = {
            2: ScatterPlot(prepared, selection, jump),
            3: Scatter3DPlot(prepared, selection, jump),
        }

    def render(self, frame: FrameContext) -> None:
        child = self.routes[self.dimensions()]
        child.height, child.fit = self.height, self.fit or child.fit
        self.children = (child,)
        super().render(frame)
        self.fit = child.fit

    def close(self) -> None:
        self.children = ()
        for child in self.routes.values():
            child.close()
