"""Immutable file/view metadata and scoped selection ports for comparison tools."""

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import polars as pl

from datelier.application.columns import ColumnChoice
from datelier.application.sources.columns import record_mapping
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.comparisons.types import ComparisonSelection
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.table import Inspection
from datelier.inspection.text.list_records import is_text_field
from datelier.inspection.text.types import TextSettings
from datelier.io.arrays.storage import ArrayStore
from datelier.io.types import ArrayOptions

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
    text: TextSettings

    @property
    def dataset(self) -> Dataset | None:
        return self.inspection.dataset if self.inspection else None


class SourceCatalog:
    def __init__(self) -> None:
        self.files: tuple[ComparisonFile, ...] = ()
        self.by_id: dict[str, ComparisonFile] = {}
        self._owners: dict[str, FileController] = {}
        self._column_choices: dict[str, tuple[ColumnChoice, ...]] = {}
        self._text_choices: dict[str, tuple[ColumnChoice, ...]] = {}
        self._image_choices: dict[str, tuple[ColumnChoice, ...]] = {}
        self.current_id = ""

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
                f.text.jobs.settings,
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
        choices = {}
        for source in self.files:
            if (
                source.identity in previous
                and previous[source.identity].inspection is source.inspection
            ):
                choices[source.identity] = self._text_choices.get(source.identity, ())
            else:
                schema = source.dataset.table.schema if source.dataset else {}
                choices[source.identity] = tuple(
                    ColumnChoice(
                        c.name,
                        c.group,
                        enabled=is_text_field(schema[c.name]),
                        reason="Text comparison requires a String or List[Text] field.",
                    )
                    for c in source.columns
                    if c.name in schema
                )
        self._text_choices = choices
        images = {}
        for source in self.files:
            previous_source = previous.get(source.identity)
            if previous_source and previous_source.inspection is source.inspection:
                images[source.identity] = self._image_choices.get(source.identity, ())
                continue
            inspection = source.inspection
            if inspection is None:
                images[source.identity] = ()
                continue
            options = inspection.imported.options
            mapping = options.mapping if isinstance(options, ArrayOptions) else None
            mapped = (
                (ColumnChoice(mapping.member, "Mapped image"),)
                if mapping and mapping.layout == ArrayLayout.IMAGE
                else ()
            )
            schema = inspection.dataset.table.schema
            images[source.identity] = mapped + tuple(
                ColumnChoice(
                    c.name,
                    c.group,
                    enabled=schema[c.name] == pl.String
                    or (
                        (m := record_mapping(inspection, c.name)) is not None
                        and m.layout == ArrayLayout.IMAGE
                    ),
                    reason="Use a reference string or confirmed image array mapping.",
                )
                for c in source.columns
                if c.name in schema
                and (not mapping or c.name not in (mapping.member, "record_index"))
            )
        self._image_choices = images

    def column_choices(self, identity: str) -> tuple[ColumnChoice, ...]:
        return self._column_choices.get(identity, ())

    def text_choices(self, identity: str) -> tuple[ColumnChoice, ...]:
        return self._text_choices.get(identity, ())

    def image_choices(self, identity: str) -> tuple[ColumnChoice, ...]:
        source = self.by_id.get(identity)
        if source is None or source.inspection is None:
            return ()
        return self._image_choices.get(identity, ())

    def open_record(
        self,
        identity: str,
        revision: DatasetRevision,
        position: int,
        row_id: int,
        column: str,
        mapped: bool,
        array_rate: int | None = None,
    ) -> None:
        file = self._owners.get(identity)
        if (
            file is None
            or file.closed
            or not file.records.open_position(
                revision, position, row_id, column, mapped
            )
        ):
            raise ValueError("The comparison source changed or closed")
        file.table.go_to(position)
        file.views = replace(file.views, tab="Inspect")
        if array_rate is not None:
            file.audio.settings = replace(
                file.audio.settings, array_sample_rate=array_rate
            )

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
        self._text_choices.clear()
        self._image_choices.clear()
