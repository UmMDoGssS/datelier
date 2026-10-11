"""Relationship content dispatches prepared chart families as immediate children."""

from collections.abc import Callable

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent


class RelationshipContent(ViewportContent):
    def __init__(
        self,
        scatter: ViewportContent,
        category: ViewportContent,
        category_active: Callable[[], bool],
    ) -> None:
        super().__init__("relationship-content")
        self.scatter, self.category, self.category_active = (
            scatter,
            category,
            category_active,
        )

    def render(self, frame: FrameContext) -> None:
        child = self.category if self.category_active() else self.scatter
        child.height, child.fit = self.height, self.fit or child.fit
        self.children = (child,)
        super().render(frame)
        self.fit = child.fit

    def close(self) -> None:
        self.children = ()
        self.scatter.close()
        self.category.close()
