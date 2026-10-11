"""Record paging composes the shared tokenization recipe fields."""

from dataclasses import replace

from datelier.application.media.records import RecordKind
from datelier.application.media.text import TextController
from datelier.gui.components.inputs import StateFields
from datelier.gui.components.layout.groups import Conditional
from datelier.gui.context.media.base import MediaSettings
from datelier.gui.context.text import TokenizationFields


class TokenSettings(MediaSettings):
    @property
    def kind(self) -> RecordKind:
        return RecordKind.TEXT

    def __init__(self, model: TextController, *, page: bool = True) -> None:
        settings = StateFields(
            lambda: model.jobs.settings,
            lambda value: setattr(model.jobs, "settings", value),
        )
        super().__init__(
            "token-settings",
            (
                TokenizationFields(
                    lambda: settings.read().tokens,
                    lambda value: settings.write(
                        replace(settings.read(), tokens=value)
                    ),
                ),
            ),
        )
        if page:
            viewport = StateFields(
                lambda: settings.read().viewport,
                lambda value: settings.write(replace(settings.read(), viewport=value)),
            )
            self.children += (
                viewport.integer(
                    "offset",
                    "Original offset",
                    lambda s: s.start,
                    lambda s, v: replace(s, start=v),
                ),
                viewport.integer(
                    "count",
                    "Code points per page",
                    lambda s: s.count,
                    lambda s, v: replace(s, count=v),
                    128,
                    8192,
                ),
                Conditional(
                    "list-element",
                    lambda: model.record_list,
                    (
                        settings.integer(
                            "element",
                            "Flattened list element (1-based)",
                            lambda s: s.element_index + 1,
                            lambda s, v: replace(s, element_index=v - 1),
                            1,
                        ),
                    ),
                ),
            )
