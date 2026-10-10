"""Explicit rendering dependencies and immediate-child composition."""

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


class Component(ABC):
    @abstractmethod
    def render(self, frame: FrameContext) -> None:
        """Render prepared state and send commands through injected interfaces."""


class BoundView[Binding](Component, ABC):
    binding: Binding | None = None

    def bind_view(self, binding: Binding) -> None:
        self.binding = binding

    def render(self, frame: FrameContext) -> None:
        if self.binding is not None:
            self.draw(self.binding, frame)

    @abstractmethod
    def draw(self, binding: Binding, frame: FrameContext) -> None:
        """Render the view's injected state and command dependencies."""


class Container(Component, ABC):
    @property
    @abstractmethod
    def children(self) -> tuple[Component, ...]:
        """The immediate children owned by this view."""

    def render(self, frame: FrameContext) -> None:
        for child in self.children:
            child.render(frame)


class Panel(Container):
    def __init__(self, key: str, children: tuple[Component, ...]) -> None:
        self.key = key
        self._children = children

    @property
    def children(self) -> tuple[Component, ...]:
        return self._children

    def render(self, frame: FrameContext) -> None:
        super().render(frame.child(self.key))
