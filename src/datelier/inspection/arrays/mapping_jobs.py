"""Header-only layout suggestions on shared workers."""

from concurrent.futures import Executor, Future
from dataclasses import replace

from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.mapping import (
    MappingSuggestion,
    SupportingArray,
    suggest_mapping,
)
from datelier.inspection.arrays.types import ArrayCatalog


def prepare_suggestion(catalog: ArrayCatalog, member: str) -> MappingSuggestion:
    suggested = suggest_mapping(catalog, member)
    supports = tuple(
        SupportingArray(name, f"value_{i}" if name == "record_index" else name[:240])
        for i, name in enumerate(suggested.supporting_members[:16])
    )
    # Archive names can share long prefixes; use unique editable column names.
    names: set[str] = set()
    unique: list[SupportingArray] = []
    for i, support in enumerate(supports):
        column = support.column
        if column in names:
            column = f"{column}_{i}"
        names.add(column)
        unique.append(replace(support, column=column))
    return replace(
        suggested, mapping=replace(suggested.mapping, supporting=tuple(unique))
    )


class MappingJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="array-mapping")
        self._future: Future[MappingSuggestion] | None = None
        self.active: MappingSuggestion | None = None
        self.message = ""

    def request(self, catalog: ArrayCatalog, member: str) -> None:
        self.abandon()
        self._future = self._executor.submit(prepare_suggestion, catalog, member)
        self.message = "Suggesting a layout from headers…"

    def poll(self) -> bool:
        if self._future is None or not self._future.done():
            return False
        future, self._future = self._future, None
        try:
            self.active = future.result()
            self.message = self.active.reason
        except ValueError as error:
            self.message = str(error)
        return True

    def abandon(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self.active = None

    def close(self) -> None:
        self.abandon()
        self._executor.shutdown(wait=False, cancel_futures=True)
