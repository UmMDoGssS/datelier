"""Worker-only exact array-cell means, with bounded reduction buffers."""

from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from datelier.core import Dataset
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.presentation import CellPresentation, NumericBounds
from datelier.inspection.records import RecordField, RecordPage, RecordSet
from datelier.inspection.records.prepare import prepare_record_page
from datelier.inspection.table import PAGE_ROWS, Inspection, PreviewPage, prepare_page
from datelier.io.arrays.storage import ArrayStore
from datelier.io.types import ArrayOptions, ImportResult

type ArrayMappings = tuple[tuple[str, ArrayRecordMapping], ...]


def array_mappings(imported: ImportResult) -> ArrayMappings:
    options, catalog = imported.options, imported.array_catalog
    if not isinstance(options, ArrayOptions) or catalog is None:
        return ()
    if options.mapping:
        return ((options.mapping.member, options.mapping),)
    return tuple(
        (name, mapping)
        for name in imported.dataset.table.columns
        if (mapping := options.mapping_for(catalog, name)) is not None
    )


def _mean_record(
    array: NDArray[np.generic],
    source_index: int,
    mapping: ArrayRecordMapping,
    stopped: Callable[[], bool],
) -> CellPresentation:
    selectors: list[int | slice] = [slice(None)] * array.ndim
    selectors[mapping.record_axis] = source_index
    values = array[tuple(selectors)]
    text = values.dtype.kind == "U"
    if values.dtype.kind not in "biufU":
        return CellPresentation(
            False, note=f"{values.dtype} elements have no scalar color mean."
        )
    count = invalid = 0
    mean = 0.0
    for chunk in np.nditer(
        values,
        flags=["external_loop", "buffered", "zerosize_ok"],
        op_flags=["readonly"],
        buffersize=16384,
    ):
        if stopped():
            raise CancelledError("Array element means abandoned")
        numeric = (
            np.array([len(str(value)) for value in chunk], dtype=np.float64)
            if text
            else np.asarray(chunk, dtype=np.float64)
        )
        finite = numeric[np.isfinite(numeric)]
        invalid += numeric.size - finite.size
        if not finite.size:
            continue
        magnitude = max(abs(float(finite.min())), abs(float(finite.max()))) or 1
        chunk_mean = float((finite / magnitude).mean()) * magnitude
        total = count + finite.size
        mean = mean * (count / total) + chunk_mean * (finite.size / total)
        count = total
    value = mean if count else None
    return CellPresentation(
        False,
        number=None if text else value,
        text_length=value if text else None,
        nonfinite=not count and invalid > 0,
        note=f"Mean of {count:,} "
        + ("text lengths" if text else "finite numeric elements")
        + (f"; {invalid:,} nonfinite elements excluded" if invalid else ""),
    )


def _prepare_array_means(
    dataset: Dataset,
    positions: tuple[int, ...],
    mappings: ArrayMappings,
    catalog: ArrayCatalog,
    store: ArrayStore,
) -> dict[str, tuple[CellPresentation, ...]]:
    """Share containing Table-page ranges; no array views escape worker leases."""
    starts = tuple(
        dict.fromkeys(position // PAGE_ROWS * PAGE_ROWS for position in positions)
    )
    windows = tuple(
        tuple(range(start, min(start + PAGE_ROWS, dataset.table.height)))
        for start in starts
    )
    expanded = tuple(position for window in windows for position in window)
    row_ids = tuple(int(dataset.row_ids[position]) for position in expanded)
    result: dict[str, tuple[CellPresentation, ...]] = {}
    for name, mapping in mappings:
        try:
            with store.open_member(catalog, mapping.member) as array:
                cells = tuple(
                    _mean_record(array, row_id, mapping, store.stop.is_set)
                    for row_id in row_ids
                )
            prepared: dict[int, CellPresentation] = {}
            offset = 0
            for window in windows:
                group = cells[offset : offset + len(window)]
                offset += len(window)
                numbers = [
                    cell.text_length if cell.text_length is not None else cell.number
                    for cell in group
                ]
                finite = np.array(
                    [value for value in numbers if value is not None], dtype=np.float64
                )
                bounds = None
                if len(finite):
                    magnitude = float(np.max(np.abs(finite))) or 1.0
                    quantiles = (
                        np.quantile(finite / magnitude, (0.02, 0.98)) * magnitude
                    )
                    bounds = NumericBounds(
                        name,
                        float(finite.min()),
                        float(finite.max()),
                        float(quantiles[0]),
                        float(quantiles[1]),
                    )
                prepared.update(
                    (
                        position,
                        replace(
                            cell,
                            bounds=bounds,
                            note=cell.note + "; automatic range uses this Table page's "
                            "record means in both views. "
                            "Use a custom range to compare pages.",
                        ),
                    )
                    for position, cell in zip(window, group, strict=True)
                )
            result[name] = tuple(prepared[position] for position in positions)
        except (ValueError, OSError, IndexError) as error:
            result[name] = tuple(
                CellPresentation(
                    False,
                    note=f"Cannot prepare element mean: {error}. "
                    "Reload the source to retry.",
                )
                for _ in positions
            )
    return result


def prepare_array_means(
    dataset: Dataset,
    positions: tuple[int, ...],
    mappings: ArrayMappings,
    catalog: ArrayCatalog,
    store: ArrayStore | None,
) -> dict[str, tuple[CellPresentation, ...]]:
    if not mappings or not positions:
        return {}
    owned = store is None
    arrays = store or ArrayStore(retained_bytes=0)
    try:
        return _prepare_array_means(dataset, positions, mappings, catalog, arrays)
    finally:
        if owned:
            arrays.close()


def prepare_array_page(
    inspection: Inspection, row_start: int, column_start: int, store: ArrayStore | None
) -> PreviewPage:
    page = prepare_page(inspection.dataset, row_start, column_start)
    mappings = tuple(
        item for item in array_mappings(inspection.imported) if item[0] in page.columns
    )
    catalog = inspection.imported.array_catalog
    if not mappings or catalog is None:
        return replace(page, array_ready=True)
    positions = tuple(range(row_start, row_start + len(page.rows)))
    means = prepare_array_means(inspection.dataset, positions, mappings, catalog, store)
    return replace(
        page,
        array_ready=True,
        cells=tuple(
            tuple(
                means[name][row] if name in means else cell
                for name, cell in zip(page.columns, cells, strict=True)
            )
            for row, cells in enumerate(page.cells)
        ),
    )


def prepare_array_record_page(
    dataset: Dataset,
    records: RecordSet,
    start: int,
    catalog: ArrayCatalog,
    mappings: ArrayMappings,
    store: ArrayStore | None,
) -> RecordPage:
    page = prepare_record_page(dataset, records, start)
    selected = set(records.settings.supporting or ())
    if records.settings.mapped_payload is not False:
        selected.update(
            name for name, _ in mappings if name not in dataset.table.columns
        )
    means = prepare_array_means(
        dataset,
        tuple(card.position for card in page.cards),
        tuple(item for item in mappings if item[0] in selected),
        catalog,
        store,
    )
    cards = []
    for row, card in enumerate(page.cards):

        def field(value: RecordField, index: int = row) -> RecordField:
            return (
                replace(value, cell=means[value.name][index])
                if value.name in means
                else value
            )

        payload = next(
            (
                RecordField(
                    name,
                    f"Array · {catalog.member(mapping.member).dtype}",
                    cell=means[name][row],
                )
                for name, mapping in mappings
                if name not in dataset.table.columns and name in means
            ),
            None,
        )
        cards.append(
            replace(
                card,
                primary=field(card.primary) if card.primary else None,
                fields=tuple(field(value) for value in card.fields),
                payload=payload,
            )
        )
    return replace(page, cards=tuple(cards))
