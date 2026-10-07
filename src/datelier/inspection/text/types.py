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
    provenance_path: str | None = None
    provenance_sha256: str | None = None

    def validate(self) -> None:
        if (
            not self.path
            or self.mode not in (TokenMode.BPE, TokenMode.UNIGRAM)
            or len(self.sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.sha256)
        ):
            raise ValueError("Invalid local tokenizer reference")
        if (self.provenance_path is None) != (self.provenance_sha256 is None):
            raise ValueError("Tokenizer provenance needs both path and digest")
        if self.provenance_sha256 is not None and (
            len(self.provenance_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.provenance_sha256)
        ):
            raise ValueError("Invalid tokenizer provenance digest")


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


class CorpusMode(StrEnum):
    RANGE = "Row range"
    SELECTION = "Linked selection"
    RANDOM = "Seeded random sample"
    COLLECTION = "All current rows"


@dataclass(frozen=True)
class TextScope:
    mode: CorpusMode = CorpusMode.RANGE
    start: int = 1
    count: int = 100
    seed: int = 42

    def validate(self) -> None:
        if min(self.start, self.count) < 1 or not 0 <= self.seed < 2**32:
            raise ValueError("Text scope needs positive range/count and a 32-bit seed")


@dataclass(frozen=True)
class TrainingSettings:
    mode: TokenMode = TokenMode.BPE
    vocabulary_size: int = 8000
    min_frequency: int = 2
    max_piece_length: int = 16
    iterations: int = 2
    shrinking_factor: float = 0.75
    special_tokens: tuple[str, ...] = ("[UNK]",)
    output_path: str = ""

    def validate(self) -> None:
        if self.mode not in (TokenMode.BPE, TokenMode.UNIGRAM):
            raise ValueError("Train BPE or Unigram")
        if not 2 <= self.vocabulary_size <= 1_000_000:
            raise ValueError("Vocabulary size must be between 2 and 1,000,000")
        if min(self.min_frequency, self.max_piece_length, self.iterations) < 1:
            raise ValueError("Training counts and lengths must be positive")
        if not 0 < self.shrinking_factor < 1:
            raise ValueError("Unigram shrinking factor must be between 0 and 1")
        if (
            not self.special_tokens
            or self.special_tokens[0] != "[UNK]"
            or len(set(self.special_tokens)) != len(self.special_tokens)
            or any(not token for token in self.special_tokens)
        ):
            raise ValueError("Distinct special tokens must start with [UNK]")


@dataclass(frozen=True)
class TextSettings:
    column: str | None = None
    source: TextSource = TextSource.AUTO
    encoding: str = "utf8"
    tokens: TokenSettings = TokenSettings()
    position: int = 0
    scope: TextScope = TextScope()
    training: TrainingSettings = TrainingSettings()
    profile_bins: int = 24

    def validate(self) -> None:
        self.tokens.validate()
        self.scope.validate()
        self.training.validate()
        if self.encoding not in ("utf8", "utf-8-sig", "utf16", "latin1"):
            raise ValueError("Choose a supported text encoding")
        if self.position < 0:
            raise ValueError("Text row position must be nonnegative")
        if not 1 <= self.profile_bins <= 200:
            raise ValueError("Text length histograms require 1–200 bins")


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
