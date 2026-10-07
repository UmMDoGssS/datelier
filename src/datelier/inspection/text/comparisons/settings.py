"""Serializable field mappings with one authoritative tokenizer configuration."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.inspection.text.types import (
    TextScope,
    TextSettings,
    TextSource,
    TokenSettings,
)


class TextScale(StrEnum):
    COUNT = "Count"
    DENSITY = "Density / proportion"


@dataclass(frozen=True)
class TextComparisonSource:
    file_id: str
    column: str
    source: TextSource = TextSource.AUTO
    encoding: str = "utf8"
    scope: TextScope = TextScope()

    def settings(self, tokens: TokenSettings) -> TextSettings:
        return TextSettings(
            self.column, self.source, self.encoding, tokens, scope=self.scope
        )

    def validate(self) -> None:
        if not self.file_id or not self.column:
            raise ValueError("Map a text field from an open file")
        self.settings(TokenSettings()).validate()


@dataclass(frozen=True)
class TextComparisonSettings:
    sources: tuple[TextComparisonSource, ...] = ()
    tokens: TokenSettings = TokenSettings()
    bins: int = 24
    scale: TextScale = TextScale.COUNT

    def validate(self) -> None:
        self.tokens.validate()
        if not 1 <= self.bins <= 200:
            raise ValueError("Text comparisons require 1–200 shared bins")
        if len(self.sources) > 32 or len({s.file_id for s in self.sources}) != len(
            self.sources
        ):
            raise ValueError("Choose one text field per file/view; at most 32 sources")
        for source in self.sources:
            source.validate()
