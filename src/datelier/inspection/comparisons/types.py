"""Small immutable plotting results with file/view/revision provenance."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.statistics import NumericStatistics


@dataclass(frozen=True)
class Origin:
    file_id: str
    revision: DatasetRevision
    column: str
    view: str = "table"


@dataclass(frozen=True)
class ComparisonInput:
    mapping: ComparisonSource
    dataset: Dataset
    filename: str

    @property
    def origin(self) -> Origin:
        return Origin(self.mapping.file_id, self.dataset.revision, self.mapping.column)


@dataclass(frozen=True)
class SeriesSummary:
    origin: Origin
    label: str
    color: tuple[float, float, float, float] | None
    counts: NDArray[np.int64]
    heights: NDArray[np.float64]
    rows: int
    included: int
    nulls: int
    nonfinite: int
    distinct: int
    mode: str = ""
    mode_count: int = 0
    statistics: NumericStatistics | None = None


@dataclass(frozen=True)
class PreparedComparison:
    settings: ComparisonSettings
    kind: ColumnRole
    series: tuple[SeriesSummary, ...]
    edges: tuple[float, ...] = ()
    scale: float = 1.0
    labels: tuple[str, ...] = ()
    keys: tuple[str | None, ...] = ()
    other: bool = False
    note: str = ""


@dataclass(frozen=True)
class ComparisonSelection:
    origin: Origin
    row_ids: tuple[int, ...]
    matches: int
    first_position: int | None
