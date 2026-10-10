"""Small prepared statistics rows beside the complete worker-owned corpus tables."""

from datelier.inspection.text.statistics import TextProfile


def statistic_rows(
    profile: TextProfile | None,
) -> tuple[tuple[str, int | float | None], ...]:
    if profile is None:
        return ()
    return (
        ("Requested source rows", profile.requested_records),
        (
            "Decoded elements" if profile.is_list else "Decoded documents",
            profile.documents,
        ),
        ("Null", profile.nulls),
        ("Empty", profile.empty),
        ("Failed", profile.failures),
        ("Counted tokens", profile.tokens),
        ("Vocabulary", profile.vocabulary_size),
        ("Original code points", profile.original_code_points),
        ("Normalized code points", profile.normalized_code_points),
        ("Inserted special tokens", profile.special_tokens),
        ("Counted special tokens", profile.counted_special_tokens),
        ("Hapax", profile.hapax),
        ("Hapax / vocabulary", profile.hapax_vocabulary_ratio),
        ("Hapax / tokens", profile.hapax_token_ratio),
        ("Type-token ratio", profile.type_token_ratio),
        ("Shannon entropy (bits)", profile.entropy_bits),
    )


def length_rows(profile: TextProfile | None) -> tuple[tuple[object, ...], ...]:
    if profile is None:
        return ()
    rows: list[tuple[object, ...]] = []
    for name, lengths in (
        ("Tokens", profile.token_lengths),
        ("Original code points", profile.character_lengths),
    ):
        quantiles = dict(lengths.quantiles)
        rows.append(
            (
                name,
                lengths.count,
                lengths.mean,
                lengths.stddev,
                lengths.minimum,
                quantiles.get(0.25),
                lengths.median,
                quantiles.get(0.75),
                quantiles.get(0.95),
                quantiles.get(0.99),
                lengths.maximum,
            )
        )
    return tuple(rows)
