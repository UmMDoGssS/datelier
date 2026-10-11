"""One correlation viewport composes typed heatmap and bounded pair-grid families."""

from collections.abc import Callable

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.relationships.correlations import CorrelationPlot
from datelier.gui.relationships.pairs import PairGrid
from datelier.plotting.relationships import Relationships
from datelier.plotting.scatter import LinkedSelection


class CorrelationContent(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Relationships | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        choose: Callable[[str, str | None], None],
        mode: Callable[[], int],
    ) -> None:
        super().__init__("correlation-content")
        self.mode = mode
        self.routes = {
            0: CorrelationPlot(prepared, choose),
            1: PairGrid(prepared, selection, jump, choose),
        }

    def render(self, frame: FrameContext) -> None:
        child = self.routes[self.mode()]
        child.height, child.fit = self.height, self.fit or child.fit
        self.children = (child,)
        super().render(frame)
        self.fit = child.fit

    def close(self) -> None:
        self.children = ()
        for child in self.routes.values():
            child.close()
