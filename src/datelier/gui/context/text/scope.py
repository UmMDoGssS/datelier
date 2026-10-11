"""Shared explicit text-record scope controls for corpus and comparison commands."""

from collections.abc import Callable
from dataclasses import replace

from datelier.gui.components.inputs import StateFields
from datelier.gui.components.layout import Group
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.text.types import CorpusMode, TextScope


class TextScopeFields(Group):
    def __init__(
        self, read: Callable[[], TextScope], write: Callable[[TextScope], None]
    ) -> None:
        fields = StateFields(read, write)
        super().__init__(
            "text-scope",
            (
                fields.choice(
                    "mode",
                    "Corpus",
                    tuple(CorpusMode),
                    lambda s: s.mode,
                    lambda s, v: replace(s, mode=v),
                ),
                Conditional(
                    "range",
                    lambda: read().mode == CorpusMode.RANGE,
                    (
                        fields.integer(
                            "start",
                            "Start row (1-based)",
                            lambda s: s.start,
                            lambda s, v: replace(s, start=v),
                            1,
                        ),
                    ),
                ),
                Conditional(
                    "bounded",
                    lambda: read().mode in (CorpusMode.RANGE, CorpusMode.RANDOM),
                    (
                        fields.integer(
                            "count",
                            "Corpus rows",
                            lambda s: s.count,
                            lambda s, v: replace(s, count=v),
                            1,
                        ),
                    ),
                ),
                Conditional(
                    "random",
                    lambda: read().mode == CorpusMode.RANDOM,
                    (
                        fields.integer(
                            "seed",
                            "Seed",
                            lambda s: s.seed,
                            lambda s, v: replace(s, seed=v),
                            0,
                            2**32 - 1,
                        ),
                    ),
                ),
            ),
        )
