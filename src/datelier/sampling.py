"""Bounded, order-independent cohorts selected by stable source identity."""

import polars as pl


def seeded_sample(frame: pl.DataFrame, limit: int, seed: int) -> pl.DataFrame:
    """Internal frames reserve `id`; tie-break hashes by ID for determinism."""
    if limit < 1 or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Sample limit must be positive; seed must be UInt32")
    if frame.height <= limit:
        return frame.sort("id")
    return (
        frame.with_columns(pl.col("id").hash(seed=seed).alias("sample_rank"))
        .bottom_k(limit, by=["sample_rank", "id"])
        .drop("sample_rank")
        .sort("id")
    )
