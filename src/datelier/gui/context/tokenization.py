"""One tokenization form for record, corpus and cross-file shared recipes."""

from collections.abc import Callable
from dataclasses import replace

from datelier.gui.components.base import Group
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.groups import Conditional
from datelier.inspection.text.types import Normalization, TokenMode, TokenSettings


class TokenizationFields(Group):
    def __init__(
        self, read: Callable[[], TokenSettings], write: Callable[[TokenSettings], None]
    ) -> None:
        fields = StateFields(read, write)
        super().__init__(
            "tokenization",
            (
                fields.choice(
                    "mode",
                    "Tokenizer",
                    tuple(TokenMode),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                fields.choice(
                    "normalization",
                    "Normalization",
                    tuple(Normalization),
                    lambda s: s.normalization,
                    lambda s, v: replace(s, normalization=v),
                ),
                fields.boolean(
                    "lowercase",
                    "Lowercase tokens",
                    lambda s: s.lowercase,
                    lambda s, v: replace(s, lowercase=v),
                ),
                Conditional(
                    "character-rule",
                    lambda: read().mode == TokenMode.CHARACTER,
                    (
                        fields.boolean(
                            "whitespace",
                            "Count whitespace code points",
                            lambda s: s.character_whitespace,
                            lambda s, v: replace(s, character_whitespace=v),
                        ),
                    ),
                ),
                Conditional(
                    "special-rules",
                    lambda: read().mode in (TokenMode.BPE, TokenMode.UNIGRAM),
                    (
                        fields.boolean(
                            "add-special",
                            "Add configured special tokens",
                            lambda s: s.add_special_tokens,
                            lambda s, v: replace(s, add_special_tokens=v),
                        ),
                        fields.boolean(
                            "count-special",
                            "Count special tokens",
                            lambda s: s.count_special_tokens,
                            lambda s, v: replace(s, count_special_tokens=v),
                        ),
                    ),
                ),
            ),
        )
