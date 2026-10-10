"""Profile families expose a typed route and render immediate children only."""

from abc import ABC, abstractmethod

from datelier.application.profiles import ProfileFamily
from datelier.gui.components.base import Container


class ProfileContent(Container, ABC):
    @property
    @abstractmethod
    def family(self) -> ProfileFamily: ...
