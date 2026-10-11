"""Generic mapped-array records reuse the source slice display family."""

from datelier.application.sources.numeric import NumericSourceController
from datelier.application.sources.records import ArrayRecordController
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.layout import FrameContext
from datelier.gui.records.base import RecordContent
from datelier.gui.sources.numeric import NumericContent


class ArrayContent(RecordContent):
    def __init__(
        self, model: ArrayRecordController, numeric: NumericSourceController
    ) -> None:
        super().__init__("array")
        self.model = model
        self.children = (
            CommandButton("prepare", "Prepare record payload", numeric.request),
            NumericContent(numeric),
        )

    def render(self, frame: FrameContext) -> None:
        if self.card and self.card.primary:
            self.model.bind_record(self.card.primary.name, self.card.row_id)
            super().render(frame)
