"""Compatible complete corpus overlays; only plotted vocabulary is bounded."""

from threading import Event

import numpy as np
import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.comparisons.types import ComparisonSelection, Origin
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextScale,
)
from datelier.inspection.text.comparisons.types import (
    PreparedTextComparison,
    TextComparisonInput,
)
from datelier.inspection.text.corpus import TextProgress, check_abandoned
from datelier.inspection.text.statistics import TextProfile, calculate_profile
from datelier.inspection.text.types import TokenMode, TokenSettings


def token_signature(settings: TokenSettings) -> tuple[object, ...]:
    # Paths/provenance labels do not change encoding; the verified JSON digest
    # includes model, vocabulary, merges, normalizers and postprocessing.
    return (
        settings.mode,
        settings.normalization,
        settings.lowercase,
        settings.character_whitespace,
        settings.add_special_tokens,
        settings.count_special_tokens,
        settings.artifact.sha256
        if settings.artifact is not None
        and settings.mode in (TokenMode.BPE, TokenMode.UNIGRAM)
        else None,
    )


def compare_profiles(
    profiles: tuple[TextProfile, ...],
    labels: tuple[str, ...],
    settings: TextComparisonSettings,
) -> PreparedTextComparison:
    settings.validate()
    if (
        len(profiles) < 2
        or len(profiles) != len(labels)
        or len(profiles) != len(settings.sources)
    ):
        raise ValueError("Prepare at least two mapped text sources")
    if any(
        token_signature(p.settings.tokens) != token_signature(settings.tokens)
        for p in profiles
    ):
        raise ValueError(
            "Incompatible tokenizers: prepare all sources with the shared configuration"
        )
    if any(
        (p.file_id, p.settings.column) != (s.file_id, s.column)
        for p, s in zip(profiles, settings.sources, strict=True)
    ):
        raise ValueError("Profile provenance does not match the mapped text sources")
    # NumPy conversions are confined to scalar plotting buffers, not source text.
    values = tuple(p.records["tokens"].drop_nulls().to_numpy() for p in profiles)
    maximum = max((int(v.max()) for v in values if len(v)), default=0)
    edges = np.linspace(0, max(1, maximum), settings.bins + 1)
    lengths = []
    frequencies = pl.concat(
        [p.frequencies.select("piece", "token_id") for p in profiles]
    ).unique()
    token_arrays, document_arrays = [], []
    for i, (p, v) in enumerate(zip(profiles, values, strict=True)):
        counts = np.histogram(v, bins=edges)[0].astype(np.float64)
        if settings.scale == TextScale.DENSITY and len(v):
            counts /= len(v) * (edges[1] - edges[0])
        lengths.append(counts)
        frequencies = frequencies.join(
            p.frequencies.rename(
                {"tokens": f"tokens_{i}", "documents": f"documents_{i}"}
            ),
            on=["piece", "token_id"],
            how="left",
            nulls_equal=True,
        ).with_columns(pl.col(f"tokens_{i}", f"documents_{i}").fill_null(0))
    frequencies = (
        frequencies.with_columns(
            pl.sum_horizontal(
                [pl.col(f"tokens_{i}") for i in range(len(profiles))]
            ).alias("total")
        )
        .sort(["total", "piece", "token_id"], descending=[True, False, False])
        .drop("total")
    )
    top = frequencies.head(12)
    for i, p in enumerate(profiles):
        tf = top[f"tokens_{i}"].to_numpy().astype(np.float64)
        df = top[f"documents_{i}"].to_numpy().astype(np.float64)
        if settings.scale == TextScale.DENSITY:
            if p.tokens:
                tf /= p.tokens
            if p.documents:
                df /= p.documents
        token_arrays.append(tf)
        document_arrays.append(df)
    return PreparedTextComparison(
        settings,
        labels,
        profiles,
        edges,
        (edges[1:] + edges[:-1]) / 2,
        tuple(lengths),
        frequencies,
        tuple(repr(piece[:60]) for piece in top["piece"]),
        np.arange(top.height, dtype=np.float64),
        tuple(
            np.arange(top.height, dtype=np.float64)
            + (i - (len(profiles) - 1) / 2) * 0.8 / len(profiles)
            for i in range(len(profiles))
        ),
        tuple(token_arrays),
        tuple(document_arrays),
    )


def prepare_comparison(
    inputs: tuple[TextComparisonInput, ...],
    settings: TextComparisonSettings,
    stop: Event,
    progress: TextProgress,
) -> PreparedTextComparison:
    if tuple(i.source for i in inputs) != settings.sources:
        raise ValueError("Mapped inputs changed")
    profiles = []
    for item in inputs:
        check_abandoned(stop)
        profiles.append(
            calculate_profile(
                item.dataset,
                item.source.file_id,
                item.source.settings(settings.tokens),
                item.selection,
                item.references,
                item.index,
                stop,
                progress,
            )
        )
    check_abandoned(stop)
    result = compare_profiles(tuple(profiles), tuple(i.label for i in inputs), settings)
    progress.update("Text comparison complete", len(inputs), len(inputs))
    return result


def select_length_bin(
    result: PreparedTextComparison, series: int, bin_index: int, dataset: Dataset
) -> ComparisonSelection:
    if not 0 <= series < len(result.profiles) or not 0 <= bin_index < len(
        result.centers
    ):
        raise ValueError("Choose a current source and length bin")
    profile = result.profiles[series]
    if profile.revision != dataset.revision:
        raise ValueError("Mapped source changed")
    lo, hi = result.edges[bin_index : bin_index + 2]
    rows = profile.records.filter(
        (pl.col("tokens") >= lo)
        & (
            pl.col("tokens") <= hi
            if bin_index == len(result.centers) - 1
            else pl.col("tokens") < hi
        )
    )["source_row_id"].unique(maintain_order=True)
    chosen = tuple(int(row) for row in rows.head(10_000))
    positions = (
        pl.DataFrame({"id": dataset.row_ids})
        .with_row_index("position")
        .filter(pl.col("id").is_in(chosen))
    )
    return ComparisonSelection(
        Origin(profile.file_id, profile.revision, profile.settings.column or ""),
        chosen,
        len(rows),
        int(positions["position"][0]) if len(positions) else None,
    )
