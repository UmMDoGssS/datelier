"""Local Tokenizers boundary; normalization retains original code-point offsets."""

import hashlib
import json
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from time import sleep

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
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = path.with_name(path.name + ".provenance.json")
    if sidecar.is_file():
        provenance = sidecar.read_bytes()
        saved = json.loads(provenance)
        if not isinstance(saved, dict) or saved.get("tokenizer_sha256") != digest:
            raise ValueError("Training provenance does not match this tokenizer")
        return TokenizerReference(
            str(path),
            digest,
            mode,
            str(sidecar),
            hashlib.sha256(provenance).hexdigest(),
        )
    return TokenizerReference(str(path), digest, mode)


def normalization(settings: TokenSettings) -> normalizers.Normalizer:
    steps: list[normalizers.Normalizer] = []
    if settings.normalization == Normalization.NFC:
        steps.append(normalizers.NFC())
    elif settings.normalization == Normalization.NFKC:
        steps.append(normalizers.NFKC())
    if settings.lowercase:
        steps.append(normalizers.Lowercase())
    return normalizers.Sequence(steps)


def source_span(
    original: str, start: int, end: int, normalizer: normalizers.Normalizer
) -> tuple[int, int]:
    # Tokenizers maps composed characters to their starter. Preserve marks
    # and Hangul Jamo consumed by normalization, without swallowing independent
    # code points. Empty-input prefixes (e.g. an imported Prepend normalizer)
    # are not evidence that two original characters composed.
    if end > start:
        while end < len(original):
            following = original[end]
            jamo = unicodedata.normalize("NFKC", following)
            if unicodedata.category(following)[0] != "M" and not any(
                0x1160 <= ord(ch) <= 0x11FF for ch in jamo
            ):
                break
            values = [
                normalizer.normalize_str(raw)
                for raw in (
                    original[start:end],
                    original[end : end + 1],
                    original[start : end + 1],
                )
            ]
            empty = normalizer.normalize_str("")
            if empty:
                values = [value.removeprefix(empty) for value in values]
            prefix, mark, combined = values
            if combined == prefix + mark:
                break
            end += 1

    return start, end


class TextTokenizer:
    """One worker-local engine reused across a corpus, with full-length encoding."""

    def __init__(self, settings: TokenSettings) -> None:
        settings.validate(require_artifact=True)
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
            if reference.provenance_path is not None:
                provenance = Path(reference.provenance_path).read_bytes()
                if (
                    hashlib.sha256(provenance).hexdigest()
                    != reference.provenance_sha256
                ):
                    raise ValueError(
                        "Training provenance changed; reload the tokenizer"
                    )
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
                start, end = source_span(text, *span, self.normalizer)
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
            for piece, span in self._builtin_splits(text):
                if (
                    self.settings.mode == TokenMode.CHARACTER
                    and not self.settings.character_whitespace
                    and piece.isspace()
                ):
                    continue
                start, end = span
                tokens.append(TextToken(piece, None, start, end))
        return TokenizedDocument(
            document,
            self.settings,
            self.normalizer.normalize_str(text),
            tuple(tokens),
            sum(t.counted for t in tokens),
        )

    def _builtin_splits(self, text: str) -> Iterator[tuple[str, tuple[int, int]]]:
        character = self.settings.mode == TokenMode.CHARACTER
        splitter = (
            pre_tokenizers.Split("", "isolated")
            if character
            else pre_tokenizers.WhitespaceSplit()
            if self.settings.mode == TokenMode.WHITESPACE
            else pre_tokenizers.Whitespace()
        )
        start = 0
        while start < len(text):
            end = min(start + 4096, len(text)) if character else len(text)
            if character and self.settings.normalization != Normalization.NONE:
                # Keep combining runs together for canonical reordering, and
                # test joins for non-mark composition such as Hangul Jamo.
                while end < len(text):
                    if unicodedata.category(text[end])[0] == "M":
                        end += 1
                        continue
                    prefix = self.normalizer.normalize_str(text[start:end])
                    suffix = self.normalizer.normalize_str(text[end : end + 1])
                    if (
                        self.normalizer.normalize_str(text[start : end + 1])
                        == prefix + suffix
                    ):
                        break
                    end += 1
            chunk = text[start:end]
            prepared = PreTokenizedString(chunk)
            prepared.normalize(self.normalizer.normalize)
            splitter.pre_tokenize(prepared)
            for piece, span, _ in prepared.get_splits("original", "char"):
                a, b = source_span(chunk, *span, self.normalizer)
                yield piece, (start + a, start + b)
            start = end
            if start < len(text):
                # Native split conversion and Python token construction need
                # periodic GIL yields while a large record is being prepared.
                sleep(0.001)
