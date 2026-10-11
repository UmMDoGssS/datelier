"""Multilingual units, original spans and reproducible local configurations."""

from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers, processors, trainers

from datelier.core.dataset import Dataset, DatasetRevision, SourceReference
from datelier.inspection.text.records import read_document
from datelier.inspection.text.tokenizers import TextTokenizer, import_tokenizer
from datelier.inspection.text.types import (
    Normalization,
    TextDocument,
    TextOrigin,
    TextSource,
    TextStatus,
    TokenMode,
    TokenSettings,
)


def document(text: str) -> TextDocument:
    dataset = Dataset.from_source(pl.DataFrame(), SourceReference(Path("text"), 0, 0))
    return TextDocument(
        TextOrigin("file", dataset.revision, 0, "text"),
        TextStatus.READY if text else TextStatus.EMPTY,
        text,
    )


@pytest.mark.parametrize("prefix_length", [2047, 4095])
@pytest.mark.parametrize(
    "original,normalized", [("e\u0301", "é"), ("가", "가"), ("각", "각")]
)
def test_composition_across_character_batches_preserves_original_spans(
    prefix_length: int, original: str, normalized: str
) -> None:
    prefix = "a" * prefix_length
    text = prefix + original + "z🙂"
    result = TextTokenizer(
        TokenSettings(TokenMode.CHARACTER, Normalization.NFC)
    ).encode(document(text))
    assert result.document.text == text
    assert result.normalized == prefix + normalized + "z🙂"
    token = result.tokens[prefix_length]
    assert token.piece == normalized
    assert (token.start, token.end) == (prefix_length, prefix_length + len(original))
    assert result.tokens[-1].end == len(text)


@pytest.mark.parametrize(
    ("mode", "pieces"),
    [
        (TokenMode.CHARACTER, list("Hi,中 🙂\n")),
        (TokenMode.WHITESPACE, ["Hi,中", "🙂"]),
        (TokenMode.WORD, ["Hi", ",", "中", "🙂"]),
    ],
)
def test_known_multilingual_units(mode: TokenMode, pieces: list[str]) -> None:
    result = TextTokenizer(TokenSettings(mode)).encode(document("Hi,中 🙂\n"))
    assert [t.piece for t in result.tokens] == pieces
    assert all(result.document.text[t.start : t.end] == t.piece for t in result.tokens)
    assert result.count == len(pieces)


def test_normalization_expansion_and_composed_original_spans() -> None:
    settings = TokenSettings(TokenMode.CHARACTER, Normalization.NFKC, lowercase=True)
    result = TextTokenizer(settings).encode(document("A e\u0301 ﬃ🙂"))
    assert result.document.text == "A e\u0301 ﬃ🙂"
    assert result.normalized == "a é ffi🙂"
    assert [result.document.text[t.start : t.end] for t in result.tokens] == [
        "A",
        " ",
        "e\u0301",
        " ",
        "ﬃ",
        "ﬃ",
        "ﬃ",
        "🙂",
    ]
    no_space = TextTokenizer(replace(settings, character_whitespace=False)).encode(
        result.document
    )
    assert no_space.count == 6


@pytest.mark.parametrize("mode", [TokenMode.BPE, TokenMode.UNIGRAM])
def test_local_round_trip_full_text_and_special_counts(
    tmp_path: Path, mode: TokenMode
) -> None:
    tokenizer = Tokenizer(
        models.BPE(unk_token="[UNK]") if mode == TokenMode.BPE else models.Unigram()
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    trainer = (
        trainers.BpeTrainer(vocab_size=50, special_tokens=["[UNK]", "[CLS]"])
        if mode == TokenMode.BPE
        else trainers.UnigramTrainer(
            vocab_size=30, special_tokens=["[UNK]", "[CLS]"], unk_token="[UNK]"
        )
    )
    tokenizer.train_from_iterator(["hello 中 é hello", "bye world"], trainer=trainer)
    cls_id = tokenizer.token_to_id("[CLS]")
    assert cls_id is not None
    tokenizer.post_processor = processors.TemplateProcessing(
        single="[CLS] $A", special_tokens=[("[CLS]", cls_id)]
    )
    tokenizer.enable_truncation(3)
    tokenizer.enable_padding(length=5)
    path = tmp_path / "local.json"
    tokenizer.save(str(path))
    reference = import_tokenizer(path)
    settings = TokenSettings(mode, add_special_tokens=True, artifact=reference)
    result = TextTokenizer(settings).encode(document("hello 中 é hello " * 40))
    assert len(result.tokens) > 100  # Imported truncation/padding cannot hide data.
    assert (
        result.tokens[0].special and result.tokens[0].start == result.tokens[0].end == 0
    )
    assert result.count == len(result.tokens) - 1
    assert TextTokenizer(replace(settings, count_special_tokens=True)).encode(
        result.document
    ).count == len(result.tokens)
    assert result == TextTokenizer(settings).encode(result.document)
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed"):
        TextTokenizer(settings)
    path.unlink()
    with pytest.raises(OSError):
        TextTokenizer(settings)


def test_distinct_null_empty_and_decode_failure_and_row_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff")
    table = pl.DataFrame({"text": [None, "", "hello", str(path)]})
    source = Dataset.from_source(table, SourceReference(tmp_path / "data.csv", 0, 0))
    dataset = source.with_rows(table.reverse(), source.row_ids.reverse())
    documents = [
        read_document(dataset, "first", "text", i, source=TextSource.INLINE)
        for i in range(4)
    ]
    assert [d.origin.row_id for d in documents] == [3, 2, 1, 0]
    assert [d.status for d in documents] == [
        TextStatus.READY,
        TextStatus.READY,
        TextStatus.EMPTY,
        TextStatus.NULL,
    ]
    failed = read_document(dataset, "first", "text", 0, source=TextSource.EXTERNAL)
    assert failed.status == TextStatus.ERROR and "utf8" in failed.diagnostic
    decoded = read_document(
        dataset, "second", "text", 0, source=TextSource.EXTERNAL, encoding="latin1"
    )
    assert decoded.text == "ÿ" and decoded.sha256 and decoded.origin.file_id == "second"
    empty = tmp_path / "empty.txt"
    empty.touch()
    empty_source = Dataset.from_source(
        pl.DataFrame({"text": [str(empty)]}), dataset.source
    )
    assert (
        read_document(
            empty_source, "empty", "text", 0, source=TextSource.EXTERNAL
        ).status
        == TextStatus.EMPTY
    )
    for doc in (documents[2], documents[3], failed):
        assert not TextTokenizer(TokenSettings()).encode(doc).tokens


def test_reject_non_text_and_unconfigured_artifacts(tmp_path: Path) -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"number": [1]}), SourceReference(tmp_path / "n.csv", 0, 0)
    )
    with pytest.raises(ValueError, match="String"):
        read_document(dataset, "file", "number", 0)
    with pytest.raises(ValueError, match="matching"):
        TextTokenizer(TokenSettings(TokenMode.BPE))
    # Origins carry revision as well as file; equal source rows are not aliases.
    assert TextOrigin("file", dataset.revision, 0, "text") != TextOrigin(
        "file", DatasetRevision(dataset.revision.dataset_id), 0, "text"
    )
