"""Exact prepared annotation summaries, distributions and linked box rows."""

from dataclasses import dataclass

import polars as pl

from datelier.inspection.annotations.association_types import PreparedAnnotations
from datelier.inspection.images.profile_types import ChannelSummary, ImageHistogram


@dataclass(frozen=True)
class ClassCount:
    id: int | str
    name: str
    count: int
    row_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class AnnotationProfile:
    source_id: str
    classes: tuple[ClassCount, ...]
    quality: tuple[tuple[str, int], ...]
    records: pl.DataFrame
    summaries: tuple[ChannelSummary, ...]
    distributions: tuple[ImageHistogram, ...]


@dataclass(frozen=True)
class AnnotationProfiles:
    annotations: PreparedAnnotations
    bins: int
    sources: tuple[AnnotationProfile, ...]
