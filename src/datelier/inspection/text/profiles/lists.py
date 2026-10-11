"""Stream string leaves with exact source-row and nested-element provenance."""

from collections.abc import Iterator
from dataclasses import replace
from threading import Event

import polars as pl

from datelier.core.column_roles import list_leaf_dtype
from datelier.core.dataset import Dataset
from datelier.inspection.text.types import TextDocument, TextOrigin, TextStatus


def is_text_list(dtype: pl.DataType) -> bool:
    return isinstance(dtype, (pl.List, pl.Array)) and list_leaf_dtype(dtype) in (
        pl.String,
        pl.Null,
    )


def is_text_field(dtype: pl.DataType) -> bool:
    return dtype == pl.String or is_text_list(dtype)


def string_elements(
    values: pl.Series, path: tuple[int, ...] = (), stop: Event | None = None
) -> Iterator[tuple[tuple[int, ...], str | None]]:
    nested = isinstance(values.dtype, (pl.List, pl.Array))
    for index in range(len(values)):
        if stop is not None and stop.is_set():
            raise ValueError("Text job abandoned")
        value = values[index]
        element = (*path, index)
        if nested:
            if isinstance(value, pl.Series):
                yield from string_elements(value, element, stop)
        elif value is None or isinstance(value, str):
            yield element, value
        else:
            raise ValueError("Text lists require string leaves")


def element_documents(
    value: object,
    origin: TextOrigin,
    stop: Event | None = None,
) -> Iterator[TextDocument]:
    if value is None:
        return
    if not isinstance(value, pl.Series):
        raise ValueError("Choose a list of text values")
    for path, text in string_elements(value, stop=stop):
        yield TextDocument(
            replace(origin, element_path=path),
            TextStatus.NULL
            if text is None
            else TextStatus.READY
            if text
            else TextStatus.EMPTY,
            text or "",
        )


def read_list_document(
    dataset: Dataset, file_id: str, column: str, position: int, element_index: int
) -> TextDocument:
    if element_index < 0:
        raise ValueError("Choose a nonnegative text element position")
    origin = TextOrigin(
        file_id, dataset.revision, int(dataset.row_ids[position]), column
    )
    value = dataset.table.get_column(column)[position]
    selected = (
        _select_element(value, element_index)
        if isinstance(value, pl.Series)
        else element_index
    )
    if isinstance(selected, tuple):
        path, text = selected
        return TextDocument(
            replace(origin, element_path=path),
            TextStatus.NULL
            if text is None
            else TextStatus.READY
            if text
            else TextStatus.EMPTY,
            text or "",
        )
    count = element_index - selected
    if count or element_index:
        raise ValueError(
            f"Selected row has {count:,} text elements; choose an available element"
        )
    null = bool(dataset.table.get_column(column).slice(position, 1).is_null().item())
    return TextDocument(
        origin,
        TextStatus.NULL if null else TextStatus.EMPTY,
        diagnostic="Selected row has no text elements (null or empty list).",
    )


def _select_element(
    values: pl.Series, index: int, path: tuple[int, ...] = ()
) -> tuple[tuple[int, ...], str | None] | int:
    """Skip preceding leaves by length without decoding their string payloads."""
    if not isinstance(values.dtype, (pl.List, pl.Array)):
        if index >= len(values):
            return index - len(values)
        value = values[index]
        if value is None or isinstance(value, str):
            return (*path, index), value
        raise ValueError("Text lists require string leaves")
    for child_index in range(len(values)):
        child = values[child_index]
        if isinstance(child, pl.Series):
            selected = _select_element(child, index, (*path, child_index))
            if isinstance(selected, tuple):
                return selected
            index = selected
    return index
