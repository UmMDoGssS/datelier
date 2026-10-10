"""Related media forms expose a typed record kind for contextual dispatch."""

from abc import ABC, abstractmethod

from datelier.application.records import RecordKind
from datelier.gui.components.base import Container


class MediaSettings(Container, ABC):
    @property
    @abstractmethod
    def kind(self) -> RecordKind: ...
