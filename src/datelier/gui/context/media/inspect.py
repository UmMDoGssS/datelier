"""Contextual inspect controls over narrow media state."""

from datelier.application.media.audio import AudioController
from datelier.application.media.images import ImageController
from datelier.application.media.records import RecordController
from datelier.application.media.text import TextController
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.context.media.audio import AudioSettings
from datelier.gui.context.media.images import ImageSettings
from datelier.gui.context.media.tokenization import TokenSettings
from datelier.gui.context.records import RecordSettings


class InspectSettings(Container):
    def __init__(
        self,
        records: RecordController,
        text: TextController,
        image: ImageController,
        audio: AudioController,
    ) -> None:
        self.records = records
        self.common = RecordSettings(records)
        forms = (TokenSettings(text), ImageSettings(image), AudioSettings(audio))
        self.registry = {form.kind: form for form in forms}
        super().__init__("inspect-settings", ())

    def render(self, frame: FrameContext) -> None:
        settings = self.registry.get(self.records.current_kind())
        self.children = (self.common, settings) if settings else (self.common,)
        super().render(frame)
