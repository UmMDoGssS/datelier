"""Contextual tokenization controls over narrow media state."""

from dataclasses import replace

from datelier.application.records import RecordKind
from datelier.application.text import TextController
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.gui.context.media.base import MediaSettings
from datelier.inspection.text.types import Normalization, TokenMode


class TokenSettings(MediaSettings):
    @property
    def kind(self) -> RecordKind:
        return RecordKind.TEXT

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
