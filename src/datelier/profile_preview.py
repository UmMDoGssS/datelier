"""Revision-aware selected profiles and shared numeric distributions."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from datelier.column_roles import ColumnRole
from datelier.dataset import Dataset, DatasetRevision
from datelier.distributions import Comparison, DistributionSettings, prepare_comparison
from datelier.plotting import Bars, prepare_bars
from datelier.profile_selection import PROFILE_ROLES
from datelier.profiling import Profiles, prepare_profiles


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
    if any(r not in PROFILE_ROLES for r in roles) or (
        len(roles) > 1 and any(r != ColumnRole.NUMERIC for r in roles)
    ):
        raise ValueError("Choose one category/date or any number of numeric columns")
    profiles = prepare_profiles(
        dataset, columns=names, bins=request.bins, top=request.top
    )
    comparison, message = None, ""
    if roles and all(r == ColumnRole.NUMERIC for r in roles):
        try:
            comparison = prepare_comparison(dataset, request.distribution, request.bins)
        except ValueError as error:
            # Keep exact statistics and the single-column histogram fallback
            # available even when shared Float64 coordinates cannot be drawn.
            message = str(error)
    return ProfileGroup(
        profiles, tuple(prepare_bars(p) for p in profiles.columns), comparison, message
    )


class ProfilePreview:
    def __init__(self) -> None:
        self.active: ProfileGroup | None = None
        self.message = ""
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="profiles"
        )
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
