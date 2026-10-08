"""Aligned NPZ record tables with member metadata as the fallback."""

from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.io.arrays.aligned import aligned_record_count, prepare_aligned_records
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.arrays.storage import ArrayStore
from datelier.io.source import read_source
from datelier.io.types import ArrayOptions, ImportFailure, ImportFormat, ImportResult


def load_arrays(path: Path, options: ArrayOptions | None = None) -> ImportResult:
    options = options or ArrayOptions()
    if options.mapping is not None:
        metadata = load_arrays(path, replace(options, mapping=None, record_table=False))
        assert metadata.array_catalog is not None
        store = ArrayStore()
        try:
            dataset, diagnostics = prepare_array_records(
                store, metadata.array_catalog, options.mapping
            )
            ArrayStore.check_source(metadata.array_catalog)
            return replace(
                metadata, dataset=dataset, options=options, diagnostics=diagnostics
            )
        except (
            ValueError,
            TypeError,
            OSError,
            IndexError,
            pl.exceptions.PolarsError,
        ) as error:
            raise ImportFailure(
                path, f"Cannot prepare array records: {error}"
            ) from error
        finally:
            store.close()
    catalog: ArrayCatalog | None = None

    def read(_source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        nonlocal catalog
        catalog = inspect_arrays(
            path, max_header_bytes=options.max_header_bytes, archive=options.archive
        )
        table = pl.DataFrame(
            {
                "member": [m.name for m in catalog.members],
                "shape": [str(m.shape) for m in catalog.members],
                "dtype": [
                    str(m.dtype) if m.dtype is not None else "unavailable"
                    for m in catalog.members
                ],
                "raw_bytes": [m.raw_bytes for m in catalog.members],
                "stored_bytes": [m.stored_bytes for m in catalog.members],
                "compressed": [m.compressed for m in catalog.members],
                "diagnostic": [m.diagnostic for m in catalog.members],
            },
            schema={
                "member": pl.String,
                "shape": pl.String,
                "dtype": pl.String,
                "raw_bytes": pl.UInt64,
                "stored_bytes": pl.UInt64,
                "compressed": pl.Boolean,
                "diagnostic": pl.String,
            },
        )
        return table, (
            "Metadata only; choose a member and Prepare slice to read values.",
            *catalog.diagnostics,
        )

    result = read_source(
        path,
        options,
        ImportFormat.ARRAY,
        read,
        "Choose a valid NPY/NPZ source or adjust the header limit.",
    )
    assert catalog is not None
    if options.record_table and aligned_record_count(catalog) is not None:
        store = ArrayStore()
        try:
            dataset, diagnostics = prepare_aligned_records(store, catalog)
            return replace(
                result, dataset=dataset, diagnostics=diagnostics, array_catalog=catalog
            )
        except (ValueError, TypeError, OSError, pl.exceptions.PolarsError) as error:
            raise ImportFailure(
                path, f"Cannot prepare NPZ record table: {error}"
            ) from error
        finally:
            store.close()
    roles = tuple(
        replace(
            info,
            inferred=ColumnRole.IDENTIFIER,
            reason="Unique array member names identify arrays within this source.",
        )
        if info.name == "member"
        else info
        for info in result.dataset.roles or ()
    )
    return replace(
        result, dataset=replace(result.dataset, roles=roles), array_catalog=catalog
    )
