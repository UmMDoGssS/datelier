"""Revision-aware selected profiles and shared numeric distributions."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass

import polars as pl

from datelier.core import Dataset, DatasetRevision, JobExecutor
from datelier.core.column_roles import LIST_ROLES, PLOTTABLE_ROLES, ColumnRole
from datelier.inspection.profiles.lists import flatten_elements
from datelier.inspection.profiles.prepare import ProfileKind, Profiles, prepare_profiles
from datelier.plotting.distributions import (
    Comparison,
    DistributionSettings,
    prepare_comparison,
    prepare_series_comparison,
)
from datelier.plotting.scatter.prepare import Bars, prepare_bars


def _numeric_list(dataset: Dataset, name: str) -> pl.Series:
    values = flatten_elements(
        dataset.table.get_column(name).gather(dataset.row_ids.arg_sort())
    )
    return values.cast(pl.Float64) if values.dtype == pl.Null else values


@dataclass(frozen=True)
class ProfileRequest:
    distribution: DistributionSettings
    bins: int = 20
    top: int = 12


@dataclass(frozen=True)
class ProfileGroup:
    profiles: Profiles
    bars: tuple[Bars, ...]
    comparison: Comparison | None
    message: str = ""


def prepare_profile_group(dataset: Dataset, request: ProfileRequest) -> ProfileGroup:
    names = request.distribution.columns
    request.distribution.validate()
    roles = tuple(dataset.role(name).role for name in names)
    if any(
        r not in (*PLOTTABLE_ROLES, *LIST_ROLES, ColumnRole.OBJECT) for r in roles
    ) or (len(roles) > 1 and any(r != ColumnRole.NUMERIC for r in roles)):
        raise ValueError("Choose one category/date/list/object or numeric columns")
    profiles = prepare_profiles(
        dataset, columns=names, bins=request.bins, top=request.top
    )
    comparison, message = None, ""
    if profiles.columns and all(
        p.kind == ProfileKind.NUMERIC for p in profiles.columns
    ):
        try:
            comparison = (
                prepare_series_comparison(
                    (_numeric_list(dataset, names[0]),),
                    request.distribution,
                    request.bins,
                )
                if len(roles) == 1 and roles[0] in LIST_ROLES
                else prepare_comparison(dataset, request.distribution, request.bins)
            )
        except ValueError as error:
            # Keep exact statistics and the single-column histogram fallback
            # available even when shared Float64 coordinates cannot be drawn.
            message = str(error)
    return ProfileGroup(
        profiles, tuple(prepare_bars(p) for p in profiles.columns), comparison, message
    )


class ProfilePreview:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self.active: ProfileGroup | None = None
        self.message = ""
        self._executor = JobExecutor(executor, max_workers=1, name="profiles")
        self._future: Future[ProfileGroup] | None = None
        self._key: tuple[DatasetRevision, ProfileRequest] | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def ensure(self, dataset: Dataset, request: ProfileRequest) -> None:
        key = (dataset.revision, request)
        if self._closed or key == self._key:
            return
        request.distribution.validate()
        self.clear()
        self._key = key
        self.message = "Preparing profiles…"
        self._future = self._executor.submit(prepare_profile_group, dataset, request)

    def poll(self, revision: DatasetRevision | None) -> None:
        if self._key is not None and self._key[0] != revision:
            self.clear()
        future = self._future
        if future is None or not future.done():
            return
        self._future = None
        try:
            self.active = future.result()
            self.message = ""
        except Exception as error:
            self.message = f"Profiles unavailable: {error}"

    def clear(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._key = None
        self.active = None
        self.message = ""

    def close(self) -> None:
        self.clear()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
