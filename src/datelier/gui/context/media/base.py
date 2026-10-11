"""Related media forms expose a typed record kind for contextual dispatch."""

from abc import ABC, abstractmethod

from datelier.application.media.records import RecordKind
from datelier.gui.components.layout import Container


class MediaSettings(Container, ABC):
    @property
    @abstractmethod
    def kind(self) -> RecordKind: ...
