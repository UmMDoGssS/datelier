"""Exact explicit-corpus statistics; only display views are bounded."""

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from threading import Event

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core import Dataset, DatasetRevision
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.text.profiles.corpus import (
    TextProgress,
    check_abandoned,
    corpus_documents,
    corpus_positions,
)
from datelier.inspection.text.profiles.lists import is_text_list
from datelier.inspection.text.tokenizers import TextTokenizer
from datelier.inspection.text.types import TextSettings, TextStatus

QUANTILES = (0.0, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0)


@dataclass(frozen=True)
class LengthStatistics:
    count: int
    mean: float | None
    stddev: float | None
    minimum: int | None
    maximum: int | None
    median: float | None
    quantiles: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class TextProfile:
    file_id: str
    revision: DatasetRevision
    settings: TextSettings
    selection: tuple[int, ...]
    requested_records: int
    documents: int
    nulls: int
    empty: int
    failures: int
    tokens: int
    special_tokens: int
    counted_special_tokens: int
    original_code_points: int
    normalized_code_points: int
    vocabulary_size: int
    hapax: int
    hapax_vocabulary_ratio: float | None
    hapax_token_ratio: float | None
    type_token_ratio: float | None
    entropy_bits: float | None
    token_lengths: LengthStatistics
    character_lengths: LengthStatistics
    records: pl.DataFrame
    frequencies: pl.DataFrame
    input_sha256: str

    @property
    def is_list(self) -> bool:
        return "element_path" in self.records.columns


def summarize_lengths(values: pl.Series) -> LengthStatistics:
    if not len(values):
        return LengthStatistics(0, None, None, None, None, None, ())
    summary = (
        pl.DataFrame({"length": values})
        .select(
            pl.col("length").mean().alias("mean"),
            pl.col("length").std(ddof=0).alias("stddev"),
            pl.col("length").min().alias("min"),
            pl.col("length").max().alias("max"),
            pl.col("length").median().alias("median"),
            *(
                pl.col("length").quantile(q, interpolation="linear").alias(str(q))
                for q in QUANTILES
            ),
        )
        .row(0)
    )
    return LengthStatistics(
        len(values),
        float(summary[0]),
        float(summary[1]),
        int(summary[2]),
        int(summary[3]),
        float(summary[4]),
        tuple(
            (q, float(value)) for q, value in zip(QUANTILES, summary[5:], strict=True)
        ),
    )


def calculate_profile(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    selection: tuple[int, ...],
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: TextProgress,
) -> TextProfile:
    settings.validate()
    tokenizer = TextTokenizer(settings.tokens)
    positions = corpus_positions(dataset, settings.scope, selection)
    term: Counter[tuple[str, int | None]] = Counter()
    document_frequency: Counter[tuple[str, int | None]] = Counter()
    records: list[tuple[int, str, int | None, int | None, int | None, str]] = []
    element_paths: list[list[int]] = []
    dtype = dataset.table.schema.get(settings.column or "")
    text_list = dtype is not None and is_text_list(dtype)
    nulls = empty = failures = tokens = special = counted_special = original = (
        normalized
    ) = 0
    digest = hashlib.sha256()
    progress.update("Profiling text", 0, len(positions))
    for doc in corpus_documents(
        dataset, file_id, settings, positions, references, index, stop, progress
    ):
        if text_list:
            element_paths.append(list(doc.origin.element_path))
        digest.update(
            json.dumps(
                [
                    (doc.origin.row_id, doc.origin.element_path)
                    if text_list
                    else doc.origin.row_id,
                    doc.status.value,
                    doc.path,
                    hashlib.sha256(doc.text.encode("utf8")).hexdigest(),
                ],
                ensure_ascii=False,
            ).encode("utf8")
        )
        if doc.status in (TextStatus.NULL, TextStatus.ERROR):
            nulls += doc.status == TextStatus.NULL
            failures += doc.status == TextStatus.ERROR
            records.append(
                (doc.origin.row_id, doc.status.value, None, None, None, doc.diagnostic)
            )
            continue
        empty += doc.status == TextStatus.EMPTY
        result = tokenizer.encode(doc)
        counts = Counter((t.piece, t.token_id) for t in result.tokens if t.counted)
        term.update(counts)
        document_frequency.update(counts.keys())
        tokens += result.count
        special += sum(t.special for t in result.tokens)
        counted_special += sum(t.special and t.counted for t in result.tokens)
        original += len(doc.text)
        normalized += len(result.normalized)
        records.append(
            (
                doc.origin.row_id,
                doc.status.value,
                result.count,
                len(doc.text),
                len(result.normalized),
                "",
            )
        )
        progress.update(
            "Profiling text elements" if text_list else "Profiling text",
            len(records),
            0 if text_list else len(positions),
        )
    check_abandoned(stop)
    rows = pl.DataFrame(
        records,
        schema={
            "source_row_id": pl.UInt64,
            "status": pl.String,
            "tokens": pl.UInt64,
            "original_code_points": pl.UInt64,
            "normalized_code_points": pl.UInt64,
            "diagnostic": pl.String,
        },
        orient="row",
    )
    if text_list:
        rows = rows.with_columns(
            pl.Series("element_path", element_paths, dtype=pl.List(pl.UInt64))
        )
    frequencies = pl.DataFrame(
        [
            (piece, token_id, count, document_frequency[(piece, token_id)])
            for (piece, token_id), count in term.items()
        ],
        schema={
            "piece": pl.String,
            "token_id": pl.Int64,
            "tokens": pl.UInt64,
            "documents": pl.UInt64,
        },
        orient="row",
    ).sort(["tokens", "piece", "token_id"], descending=[True, False, False])
    vocabulary = len(term)
    hapax = sum(count == 1 for count in term.values())
    entropy = (
        -math.fsum(
            (count / tokens) * math.log2(count / tokens) for count in term.values()
        )
        if tokens
        else None
    )
    progress.update("Profile complete", len(positions), len(positions))
    return TextProfile(
        file_id,
        dataset.revision,
        settings,
        selection,
        len(positions),
        len(records) - nulls - failures,
        nulls,
        empty,
        failures,
        tokens,
        special,
        counted_special,
        original,
        normalized,
        vocabulary,
        hapax,
        hapax / vocabulary if vocabulary else None,
        hapax / tokens if tokens else None,
        vocabulary / tokens if tokens else None,
        entropy,
        summarize_lengths(rows.get_column("tokens").drop_nulls()),
        summarize_lengths(rows.get_column("original_code_points").drop_nulls()),
        rows,
        frequencies,
        digest.hexdigest(),
    )


def length_histogram(
    profile: TextProfile, bins: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if not 1 <= bins <= 200:
        raise ValueError("Choose between 1 and 200 length bins")
    # Conversion is confined to this statistical plotting boundary; source
    # text remains in Polars and only prepared scalar lengths reach NumPy.
    counts, edges = np.histogram(
        profile.records.get_column("tokens").drop_nulls().to_numpy(), bins=bins
    )
    return counts.astype(np.float64), edges
