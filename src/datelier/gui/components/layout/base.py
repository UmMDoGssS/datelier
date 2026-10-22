"""One rendering contract; containers own and render their direct children."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from datelier.gui.components.probe import GuiProbe, ViewScope


@dataclass(frozen=True)
class FrameContext:
    scope: ViewScope
    probe: GuiProbe
    path: tuple[str, ...] = ()

    def child(self, key: str) -> FrameContext:
        return replace(self, path=(*self.path, key))

    def record(self, key: str, point: tuple[float, float]) -> None:
        self.probe.record(self.scope, (*self.path, key), point)

    def measure(self, key: str, values: tuple[float, float]) -> None:
        self.probe.measure(self.scope, (*self.path, key), values)


class Component(ABC):
    """Render prepared state under a scoped native/probe identity.

    Containers invoke immediate children. Components owning native resources must
    release them in close before the renderer shuts down.
    """

    def __init__(self, key: str) -> None:
        self.key = key

    @abstractmethod
    def render(self, frame: FrameContext) -> None: ...

    def close(self) -> None:
        """Release native resources before the renderer shuts down."""
        return


class Container(Component, ABC):
    def __init__(self, key: str, children: tuple[Component, ...]) -> None:
        super().__init__(key)
        self.children = children

    def render(self, frame: FrameContext) -> None:
        for child in self.children:
            child.render(frame.child(child.key))

    def close(self) -> None:
        for child in self.children:
            child.close()


class Page(Container, ABC):
    """Application-level composition."""


class Group(Container):
    """Concrete composition of immediate children without a specialized view."""


class SharedView(Group):
    """Render a direct child whose native lifetime belongs to the page owner."""

    def __init__(self, content: Component) -> None:
        super().__init__("shared", (content,))

    def close(self) -> None:
        self.children = ()


class Panel(Container, ABC):
    """A dockable or drawer-hosted region."""


class Tab(Container, ABC):
    """A named route containing its own immediate content."""
