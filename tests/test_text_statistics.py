"""Hand-calculated exact corpus statistics and distinct excluded outcomes."""

import math
from dataclasses import replace
from pathlib import Path
from threading import Event

import polars as pl
import pytest
from tokenizers import Tokenizer, models, processors

from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.corpus import TextProgress
from datelier.inspection.text.statistics import calculate_profile, length_histogram
from datelier.inspection.text.tokenization import import_tokenizer
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
)
from datelier.io.importing import load_file


def test_known_token_document_hapax_entropy_and_lengths(tmp_path: Path) -> None:
    source = tmp_path / "corpus.csv"
    pl.DataFrame({"id": range(5), "text": ["a a b", "b c", "", None, "a"]}).write_csv(
        source
    )
    dataset = load_file(source).dataset
    settings = TextSettings(
        "text", TextSource.INLINE, scope=TextScope(CorpusMode.COLLECTION)
    )
    result = calculate_profile(
        dataset,
        "file",
        settings,
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert (
        result.requested_records,
        result.documents,
        result.nulls,
        result.empty,
        result.failures,
    ) == (5, 4, 1, 1, 0)
    assert result.tokens == 6 and result.vocabulary_size == 3 and result.hapax == 1
    assert result.hapax_vocabulary_ratio == 1 / 3
    assert result.type_token_ratio == 0.5 and result.hapax_token_ratio == 1 / 6
    assert result.entropy_bits == pytest.approx(
        -(0.5 * math.log2(0.5) + 1 / 3 * math.log2(1 / 3) + 1 / 6 * math.log2(1 / 6))
    )
    assert result.frequencies.select("piece", "tokens", "documents").rows() == [
        ("a", 3, 2),
        ("b", 2, 2),
        ("c", 1, 1),
    ]
    lengths = result.token_lengths
    assert (lengths.minimum, lengths.maximum, lengths.median, lengths.mean) == (
        0,
        3,
        1.5,
        1.5,
    )
    assert lengths.stddev == pytest.approx(math.sqrt(1.25))
    assert (
        dict(lengths.quantiles)[0.25] == 0.75 and dict(lengths.quantiles)[0.75] == 2.25
    )
    counts, edges = length_histogram(result, 3)
    assert sum(counts) == 4 and len(edges) == 4
    # Scope uses current positions while result records retain source identity.
    reversed_data = dataset.with_rows(
        dataset.table.reverse(), dataset.row_ids.reverse()
    )
    chosen = calculate_profile(
        reversed_data,
        "second",
        replace(settings, scope=TextScope(CorpusMode.SELECTION)),
        (0, 4),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert chosen.records["source_row_id"].to_list() == [4, 0]
    assert chosen.file_id == "second" and chosen.tokens == 4


def test_empty_corpus_and_decode_errors_are_not_zero_length_documents(
    tmp_path: Path,
) -> None:
    broken = tmp_path / "bad.txt"
    broken.write_bytes(b"\xff")
    empty = tmp_path / "empty.txt"
    empty.touch()
    source = tmp_path / "corpus.csv"
    pl.DataFrame({"text": [str(broken), str(empty), None]}).write_csv(source)
    dataset = load_file(source).dataset
    settings = TextSettings("text", TextSource.EXTERNAL)
    result = calculate_profile(
        dataset,
        "file",
        settings,
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert (result.failures, result.nulls, result.empty, result.documents) == (
        1,
        1,
        1,
        1,
    )
    assert result.token_lengths.count == 1 and result.token_lengths.mean == 0
    assert result.tokens == result.vocabulary_size == result.hapax == 0
    assert (
        result.entropy_bits
        is result.type_token_ratio
        is result.hapax_token_ratio
        is None
    )
    assert "Cannot decode text" in result.records["diagnostic"][0]
    no_rows = calculate_profile(
        dataset,
        "file",
        replace(settings, scope=TextScope(CorpusMode.RANGE, 100, 2)),
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert no_rows.requested_records == 0 and no_rows.token_lengths.mean is None
    stop = Event()
    stop.set()
    with pytest.raises(ValueError, match="abandoned"):
        calculate_profile(
            dataset,
            "file",
            settings,
            (),
            ReferenceSettings(),
            None,
            stop,
            TextProgress(),
        )


def test_special_token_policy_affects_all_totals_and_frequencies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.csv"
    pl.DataFrame({"text": ["a", ""]}).write_csv(source)
    dataset = load_file(source).dataset
    tokenizer = Tokenizer(models.BPE({"a": 0, "[CLS]": 1}, []))
    tokenizer.post_processor = processors.TemplateProcessing(
        single="[CLS] $A", special_tokens=[("[CLS]", 1)]
    )
    path = tmp_path / "tokenizer.json"
    tokenizer.save(str(path))
    settings = TextSettings(
        "text",
        TextSource.INLINE,
        tokens=TokenSettings(
            TokenMode.BPE, add_special_tokens=True, artifact=import_tokenizer(path)
        ),
    )
    result = calculate_profile(
        dataset,
        "file",
        settings,
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert (result.tokens, result.special_tokens, result.counted_special_tokens) == (
        1,
        2,
        0,
    )
    assert result.frequencies["piece"].to_list() == ["a"]
    included = calculate_profile(
        dataset,
        "file",
        replace(settings, tokens=replace(settings.tokens, count_special_tokens=True)),
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    assert included.tokens == 3 and included.counted_special_tokens == 2
    assert included.frequencies.select("piece", "tokens", "documents").rows() == [
        ("[CLS]", 2, 2),
        ("a", 1, 1),
    ]
