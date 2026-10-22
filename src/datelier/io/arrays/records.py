"""Explicit mapped records: Polars scalar support, referenced array payloads."""

from dataclasses import replace
from typing import cast

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core import ColumnRole, Dataset
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.io.arrays.storage import ArrayStore


def _supporting_series(
    name: str, array: NDArray[np.generic]
) -> tuple[pl.Series, str | None]:
    dtype = array.dtype
    if dtype.kind in "biuf" and dtype.itemsize <= 8:
        native = array.astype(dtype.newbyteorder("="), copy=True)
        if dtype.kind == "f" and dtype.itemsize == 2:
            native = native.astype(np.float32)
        return (
            pl.Series(name, native),
            "float16 represented exactly as Float32"
            if dtype.kind == "f" and dtype.itemsize == 2
            else None,
        )
    if dtype.kind in "US":
        return pl.Series(
            name, array.tolist(), dtype=pl.String if dtype.kind == "U" else pl.Binary
        ), None
    if dtype.kind in "Mm":
        return pl.Series(name, array.copy()), None
    # Polars has no scalar complex/extended-float/void dtype. Preserve their
    # readable scalar values as text rather than silently narrowing precision.
    return pl.Series(
        name, [str(value) for value in array], dtype=pl.String
    ), f"{dtype} supporting values represented as text"


def prepare_array_records(
    store: ArrayStore, catalog: ArrayCatalog, mapping: ArrayRecordMapping
) -> tuple[Dataset, tuple[str, ...]]:
    count = mapping.record_count(catalog)
    columns = [pl.Series("record_index", range(count), dtype=pl.UInt64)]
    diagnostics: list[str] = [
        f"Referenced {mapping.member}; source indices are original "
        f"axis {mapping.record_axis} positions."
    ]
    for support in mapping.supporting:
        metadata = catalog.member(support.member)
        selectors: list[int | slice] = list(support.fixed or (0,) * len(metadata.shape))
        selectors[support.record_axis] = slice(None)
        with store.open_member(catalog, support.member) as array:
            selected = np.asarray(array[tuple(selectors)])
            if support.field is not None:
                if (
                    selected.dtype.names is None
                    or support.field not in selected.dtype.names
                ):
                    raise ValueError(
                        f"{support.column}: selected structured field is unavailable"
                    )
                selected = cast(
                    NDArray[np.generic], cast(NDArray[np.void], selected)[support.field]
                )
            if selected.ndim != 1:
                raise ValueError(
                    f"{support.column}: choose a scalar supporting field/coordinate"
                )
            series, diagnostic = _supporting_series(support.column, selected)
            columns.append(series)
            if diagnostic:
                diagnostics.append(
                    f"{support.column}: {diagnostic}. "
                    f"Original array dtype is {metadata.dtype}."
                )
    dataset = Dataset.from_source(pl.DataFrame(columns), catalog.source)
    dataset = replace(
        dataset,
        roles=tuple(
            replace(
                info,
                inferred=ColumnRole.IDENTIFIER,
                reason="Original mapped record-axis indices retain source provenance.",
            )
            if info.name == "record_index"
            else info
            for info in dataset.roles or ()
        ),
    )
    return dataset, tuple(diagnostics)
