"""Local Tokenizers boundary; normalization retains original code-point offsets."""

import hashlib
import json
import unicodedata
from pathlib import Path

from tokenizers import PreTokenizedString, Tokenizer, normalizers, pre_tokenizers
from tokenizers.models import BPE

from datelier.inspection.text.types import (
    Normalization,
    TextDocument,
    TextStatus,
    TextToken,
    TokenizedDocument,
    TokenizerReference,
    TokenMode,
    TokenSettings,
)


def import_tokenizer(path: Path) -> TokenizerReference:
    """Validate a local artifact; never consult the Hub or train a model."""
    path = path.expanduser().resolve()
    payload = path.read_bytes()
    tokenizer = Tokenizer.from_str(payload.decode("utf8"))
    mode = TokenMode(json.loads(tokenizer.to_str())["model"]["type"])
    if mode not in (TokenMode.BPE, TokenMode.UNIGRAM):
        raise ValueError("Choose a BPE or Unigram tokenizer JSON")
    return TokenizerReference(str(path), hashlib.sha256(payload).hexdigest(), mode)


def normalization(settings: TokenSettings) -> normalizers.Normalizer:
    steps: list[normalizers.Normalizer] = []
    if settings.normalization == Normalization.NFC:
        steps.append(normalizers.NFC())
    elif settings.normalization == Normalization.NFKC:
        steps.append(normalizers.NFKC())
    if settings.lowercase:
        steps.append(normalizers.Lowercase())
    return normalizers.Sequence(steps)


def source_span(original: str, start: int, end: int) -> tuple[int, int]:
    # Tokenizers maps a composed character to its starter. Include trailing
    # source combining marks so highlighting covers the original sequence.
    if end > start:
        while end < len(original) and unicodedata.category(original[end])[0] == "M":
            end += 1
    return start, end


class TextTokenizer:
    """One worker-local engine reused across a corpus, with full-length encoding."""

    def __init__(self, settings: TokenSettings) -> None:
        settings.validate()
        self.settings = settings
        self.normalizer = normalization(settings)
        self.tokenizer: Tokenizer | None = None
        if settings.mode in (TokenMode.BPE, TokenMode.UNIGRAM):
            reference = settings.artifact
            assert reference is not None
            payload = Path(reference.path).read_bytes()
            if hashlib.sha256(payload).hexdigest() != reference.sha256:
                raise ValueError(
                    "Tokenizer changed; explicitly reload its configuration"
                )
            tokenizer = Tokenizer.from_str(payload.decode("utf8"))
            if (
                TokenMode(json.loads(tokenizer.to_str())["model"]["type"])
                != settings.mode
            ):
                raise ValueError("Tokenizer model does not match the saved mode")
            embedded = tokenizer.normalizer
            if embedded is not None:
                self.normalizer = normalizers.Sequence([self.normalizer, embedded])
            tokenizer.normalizer = self.normalizer
            tokenizer.no_truncation()
            tokenizer.no_padding()
            if isinstance(tokenizer.model, BPE):
                tokenizer.model.dropout = None
            self.tokenizer = tokenizer

    def encode(self, document: TextDocument) -> TokenizedDocument:
        text = document.text
        if document.status in (TextStatus.NULL, TextStatus.ERROR):
            return TokenizedDocument(document, self.settings, "", ())
        tokens: list[TextToken] = []
        if self.tokenizer is not None:
            encoding = self.tokenizer.encode(
                text, add_special_tokens=self.settings.add_special_tokens
            )
            for piece, token_id, span, special in zip(
                encoding.tokens,
                encoding.ids,
                encoding.offsets,
                encoding.special_tokens_mask,
                strict=True,
            ):
                start, end = source_span(text, *span)
                tokens.append(
                    TextToken(
                        piece,
                        token_id,
                        start,
                        end,
                        bool(special),
                        not special or self.settings.count_special_tokens,
                    )
                )
        else:
            prepared = PreTokenizedString(text)
            prepared.normalize(self.normalizer.normalize)
            splitter = (
                pre_tokenizers.Split("", "isolated")
                if self.settings.mode == TokenMode.CHARACTER
                else pre_tokenizers.WhitespaceSplit()
                if self.settings.mode == TokenMode.WHITESPACE
                else pre_tokenizers.Whitespace()
            )
            splitter.pre_tokenize(prepared)
            for piece, span, _ in prepared.get_splits("original", "char"):
                if (
                    self.settings.mode == TokenMode.CHARACTER
                    and not self.settings.character_whitespace
                    and piece.isspace()
                ):
                    continue
                start, end = source_span(text, *span)
                tokens.append(TextToken(piece, None, start, end))
        return TokenizedDocument(
            document,
            self.settings,
            self.normalizer.normalize_str(text),
            tuple(tokens),
        )
