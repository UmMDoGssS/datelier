"""Immutable file/view metadata and scoped selection ports for comparison tools."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from datelier.application.columns import ColumnChoice
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.comparisons.types import ComparisonSelection
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.table import Inspection
from datelier.io.arrays.storage import ArrayStore

if TYPE_CHECKING:
    from datelier.application.file import FileController


@dataclass(frozen=True)
class ComparisonFile:
    identity: str
    title: str
    view_name: str
    inspection: Inspection | None
    columns: tuple[ColumnChoice, ...]
    references: ReferenceSettings
    index: ReferenceIndex | None
    selection: tuple[int, ...]
    arrays: ArrayStore

    @property
    def dataset(self) -> Dataset | None:
        return self.inspection.dataset if self.inspection else None


class SourceCatalog:
    def __init__(self) -> None:
        self.files: tuple[ComparisonFile, ...] = ()
        self.by_id: dict[str, ComparisonFile] = {}
        self._owners: dict[str, FileController] = {}
        self._column_choices: dict[str, tuple[ColumnChoice, ...]] = {}

    @property
    def datasets(self) -> dict[str, Dataset]:
        return {f.identity: f.dataset for f in self.files if f.dataset is not None}

    def sync(self, files: tuple[FileController, ...]) -> None:
        previous = self.by_id
        self._owners = {f.identity: f for f in files if not f.closed}
        self.files = tuple(
            ComparisonFile(
                f.identity,
                (f.inspection.dataset.source.path.name if f.inspection else f.title)
                + (f" · {f.view_name}" if f.view_name else ""),
                f.view_name,
                f.inspection,
                f.choices,
                f.references.settings,
                f.references.index,
                f.media_input().selected_rows,
                f.arrays.store,
            )
            for f in self._owners.values()
        )
        self.by_id = {f.identity: f for f in self.files}
        self._column_choices = {
            f.identity: self._column_choices.get(f.identity, ())
            if f.identity in previous
            and previous[f.identity].inspection is f.inspection
            else tuple(
                ColumnChoice(
                    c.name,
                    c.group,
                    c.numeric,
                    c.group in (ColumnRole.NUMERIC.value, ColumnRole.CATEGORY.value),
                    "Use Numeric or Categorical interpretations "
                    "for column comparisons.",
                )
                for c in f.columns
            )
            if f.dataset
            else ()
            for f in self.files
        }

    def column_choices(self, identity: str) -> tuple[ColumnChoice, ...]:
        return self._column_choices.get(identity, ())

    def apply_selection(self, selection: ComparisonSelection) -> None:
        file = self._owners.get(selection.origin.file_id)
        if (
            file is None
            or file.closed
            or file.loader.revision != selection.origin.revision
        ):
            return
        file.selection.choose(selection.origin.revision, selection.row_ids)
        file.selection.message = (
            f"{len(selection.row_ids):,} of "
            f"{selection.matches:,} matching source rows selected."
        )
        if selection.first_position is not None:
            file.table.go_to(selection.first_position)

    def close(self) -> None:
        self.files = ()
        self.by_id.clear()
        self._owners.clear()
        self._column_choices.clear()
