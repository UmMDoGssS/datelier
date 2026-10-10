"""Focused media controls share field families and keep commands explicit."""

from dataclasses import replace

from datelier.application.audio import AudioController
from datelier.application.images import ImageController
from datelier.application.records import RecordController, RecordKind
from datelier.application.text import TextController
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.gui.context.records import RecordSettings
from datelier.inspection.heatmaps import Colormap
from datelier.inspection.text.types import Normalization, TokenMode


class TokenSettings(Container):
    def __init__(self, model: TextController, *, page: bool = True) -> None:
        super().__init__(
            "token-settings",
            (
                ChoiceField(
                    "mode",
                    "Tokenizer",
                    tuple(TokenMode),
                    lambda: model.jobs.settings.tokens.mode,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            tokens=replace(model.jobs.settings.tokens, mode=value),
                        ),
                    ),
                ),
                ChoiceField(
                    "normalization",
                    "Normalization",
                    tuple(Normalization),
                    lambda: model.jobs.settings.tokens.normalization,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            tokens=replace(
                                model.jobs.settings.tokens, normalization=value
                            ),
                        ),
                    ),
                ),
                BooleanField(
                    "lowercase",
                    "Lowercase tokens",
                    lambda: model.jobs.settings.tokens.lowercase,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            tokens=replace(model.jobs.settings.tokens, lowercase=value),
                        ),
                    ),
                ),
                IntegerField(
                    "offset",
                    "Original offset",
                    lambda: model.jobs.settings.viewport.start,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            viewport=replace(model.jobs.settings.viewport, start=value),
                        ),
                    ),
                    0,
                ),
                IntegerField(
                    "count",
                    "Code points per page",
                    lambda: model.jobs.settings.viewport.count,
                    lambda value: setattr(
                        model.jobs,
                        "settings",
                        replace(
                            model.jobs.settings,
                            viewport=replace(model.jobs.settings.viewport, count=value),
                        ),
                    ),
                    128,
                    8192,
                ),
            ),
        )

        if not page:
            self.children = self.children[:-2]
        else:
            self.children += (
                Conditional(
                    "list-element",
                    lambda: model.record_list,
                    (
                        IntegerField(
                            "element",
                            "Flattened list element (1-based)",
                            lambda: model.jobs.settings.element_index + 1,
                            lambda value: setattr(
                                model.jobs,
                                "settings",
                                replace(model.jobs.settings, element_index=value - 1),
                            ),
                            1,
                        ),
                    ),
                ),
            )
        self.children += (
            BooleanField(
                "whitespace",
                "Count whitespace code points",
                lambda: model.jobs.settings.tokens.character_whitespace,
                lambda value: setattr(
                    model.jobs,
                    "settings",
                    replace(
                        model.jobs.settings,
                        tokens=replace(
                            model.jobs.settings.tokens, character_whitespace=value
                        ),
                    ),
                ),
            ),
            BooleanField(
                "add-special",
                "Add configured special tokens",
                lambda: model.jobs.settings.tokens.add_special_tokens,
                lambda value: setattr(
                    model.jobs,
                    "settings",
                    replace(
                        model.jobs.settings,
                        tokens=replace(
                            model.jobs.settings.tokens, add_special_tokens=value
                        ),
                    ),
                ),
            ),
            BooleanField(
                "count-special",
                "Count special tokens",
                lambda: model.jobs.settings.tokens.count_special_tokens,
                lambda value: setattr(
                    model.jobs,
                    "settings",
                    replace(
                        model.jobs.settings,
                        tokens=replace(
                            model.jobs.settings.tokens, count_special_tokens=value
                        ),
                    ),
                ),
            ),
        )

        rules = self.children[-3:]
        self.children = (
            *self.children[:-3],
            Conditional(
                "character-rule",
                lambda: model.jobs.settings.tokens.mode == TokenMode.CHARACTER,
                (rules[0],),
            ),
            Conditional(
                "special-rules",
                lambda: (
                    model.jobs.settings.tokens.mode
                    in (TokenMode.BPE, TokenMode.UNIGRAM)
                ),
                rules[1:],
            ),
        )


class ImageSettings(Container):
    def __init__(self, model: ImageController) -> None:
        super().__init__("image-settings", ())
        self.model = model
        self.channel: ChoiceField[int | None] | None = None
        self._count = -1
        self.colormap = ChoiceField(
            "colormap",
            "Heatmap colors",
            tuple(Colormap),
            lambda: model.settings.display.colormap,
            lambda value: setattr(
                model,
                "settings",
                replace(
                    model.settings,
                    display=replace(model.settings.display, colormap=value),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        prepared = self.model.jobs.metadata
        count = prepared[1].count if prepared else 0
        if self._count != count:
            self._count = count
            self.channel = ChoiceField(
                "channel",
                "Channel",
                (None, *range(count)),
                lambda: self.model.settings.display.channel,
                lambda value: setattr(
                    self.model,
                    "settings",
                    replace(
                        self.model.settings,
                        display=replace(self.model.settings.display, channel=value),
                    ),
                ),
                ("All channels", *(str(i) for i in range(count))),
            )
        self.children = (
            (self.channel, self.colormap) if self.channel else (self.colormap,)
        )
        super().render(frame)


class AudioSettings(Container):
    def __init__(self, model: AudioController) -> None:
        super().__init__(
            "audio-settings",
            (
                IntegerField(
                    "start",
                    "First sample frame",
                    lambda: model.settings.range.start,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            range=replace(model.settings.range, start=value),
                        ),
                    ),
                    0,
                ),
                IntegerField(
                    "stop",
                    "Last sample frame",
                    lambda: model.settings.range.stop or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(
                            model.settings,
                            range=replace(model.settings.range, stop=value or None),
                        ),
                    ),
                    0,
                ),
                IntegerField(
                    "channel",
                    "Channel (0-based)",
                    lambda: model.settings.channel,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, channel=value)
                    ),
                    0,
                ),
                IntegerField(
                    "array-rate",
                    "Array sample rate (0 = unknown)",
                    lambda: model.settings.array_sample_rate or 0,
                    lambda value: setattr(
                        model,
                        "settings",
                        replace(model.settings, array_sample_rate=value or None),
                    ),
                    0,
                    768000,
                ),
            ),
        )


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
        self.registry = {
            RecordKind.TEXT: TokenSettings(text),
            RecordKind.IMAGE: ImageSettings(image),
            RecordKind.AUDIO: AudioSettings(audio),
        }
        super().__init__("inspect-settings", ())

    def render(self, frame: FrameContext) -> None:
        settings = self.registry.get(self.records.current_kind())
        self.children = (self.common, settings) if settings else (self.common,)
        super().render(frame)
