"""Text recipes and source-aligned prepared tokens, independent of the GUI."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.core.dataset import DatasetRevision


class TokenMode(StrEnum):
    CHARACTER = "Character"
    WHITESPACE = "Whitespace"
    WORD = "Word"
    BPE = "BPE"
    UNIGRAM = "Unigram"


class Normalization(StrEnum):
    NONE = "None"
    NFC = "NFC"
    NFKC = "NFKC"


@dataclass(frozen=True)
class TokenizerReference:
    path: str
    sha256: str
    mode: TokenMode

    def validate(self) -> None:
        if (
            not self.path
            or self.mode not in (TokenMode.BPE, TokenMode.UNIGRAM)
            or len(self.sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.sha256)
        ):
            raise ValueError("Invalid local tokenizer reference")


@dataclass(frozen=True)
class TokenSettings:
    mode: TokenMode = TokenMode.WORD
    normalization: Normalization = Normalization.NONE
    lowercase: bool = False
    character_whitespace: bool = True
    add_special_tokens: bool = False
    count_special_tokens: bool = False
    artifact: TokenizerReference | None = None

    def validate(self, *, require_artifact: bool = False) -> None:
        if self.artifact is not None:
            self.artifact.validate()
        if (
            require_artifact
            and self.mode in (TokenMode.BPE, TokenMode.UNIGRAM)
            and (self.artifact is None or self.artifact.mode != self.mode)
        ):
            raise ValueError("Load a matching local tokenizer JSON configuration")


class TextStatus(StrEnum):
    READY = "Ready"
    EMPTY = "Empty"
    NULL = "Null"
    ERROR = "Error"


class TextSource(StrEnum):
    AUTO = "By interpretation"
    INLINE = "Inline value"
    EXTERNAL = "External file"


@dataclass(frozen=True)
class TextSettings:
    column: str | None = None
    source: TextSource = TextSource.AUTO
    encoding: str = "utf8"
    tokens: TokenSettings = TokenSettings()
    position: int = 0

    def validate(self) -> None:
        self.tokens.validate()
        if self.encoding not in ("utf8", "utf-8-sig", "utf16", "latin1"):
            raise ValueError("Choose a supported text encoding")
        if self.position < 0:
            raise ValueError("Text row position must be nonnegative")


@dataclass(frozen=True)
class TextOrigin:
    file_id: str
    revision: DatasetRevision
    row_id: int
    column: str


@dataclass(frozen=True)
class TextDocument:
    origin: TextOrigin
    status: TextStatus
    text: str = ""
    diagnostic: str = ""
    path: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class TextToken:
    piece: str
    token_id: int | None
    start: int
    end: int
    special: bool = False
    counted: bool = True


@dataclass(frozen=True)
class TokenizedDocument:
    document: TextDocument
    settings: TokenSettings
    normalized: str
    tokens: tuple[TextToken, ...]
    count: int = 0
