"""Scoped record-content family; immutable cards are presentation bindings."""

from abc import ABC, abstractmethod

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.inspection.records.types import RecordCard


class RecordContent(ViewportContent, ABC):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.card: RecordCard | None = None

    def bind_record(self, card: RecordCard) -> None:
        self.card = card

    @abstractmethod
    def render(self, frame: FrameContext) -> None:
        super().render(frame)

    def close(self) -> None:
        self.card = None
        super().close()
