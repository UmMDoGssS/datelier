"""Prepared route dispatch to immediate children."""

from collections.abc import Callable

from datelier.gui.components.layout.base import Component, Container, FrameContext


class RoutedContent(Container):
    def __init__(
        self, routes: dict[str, Component], selected: Callable[[], str]
    ) -> None:
        super().__init__("view", ())
        self.routes = routes
        self.selected = selected

    def render(self, frame: FrameContext) -> None:
        # Assembly supplies the navigation provider explicitly.
        route = self.selected()
        child = self.routes.get(route)
        self.children = (child,) if child else ()
        super().render(frame)

    def close(self) -> None:
        for child in self.routes.values():
            child.close()
        self.children = ()
