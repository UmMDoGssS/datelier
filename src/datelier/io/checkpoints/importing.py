"""Read-only CPU checkpoint metadata import and tensor provenance."""

from dataclasses import replace
from pathlib import Path
from typing import BinaryIO
from zipfile import is_zipfile

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.inspection.checkpoints.types import CheckpointCatalog, TensorInfo
from datelier.inspection.objects.types import ObjectNode
from datelier.io.checkpoints.metadata import checkpoint_tree
from datelier.io.checkpoints.runtime import load_restricted
from datelier.io.source import read_source
from datelier.io.types import CheckpointOptions, ImportFormat, ImportResult


def load_checkpoint(
    path: Path, options: CheckpointOptions | None = None
) -> ImportResult:
    options = options or CheckpointOptions()
    path = path.expanduser().resolve()
    root: ObjectNode | None = None
    tensors: tuple[TensorInfo, ...] = ()
    mapped = False

    def read(_source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        nonlocal root, tensors, mapped
        value = load_restricted(path, metadata=True)
        root, tensors = checkpoint_tree(
            value, max_nodes=options.max_nodes, max_depth=options.max_depth
        )
        mapped = is_zipfile(path)
        table = pl.DataFrame(
            {
                "tensor": [t.name for t in tensors],
                "shape": [str(t.shape) for t in tensors],
                "dtype": [t.dtype for t in tensors],
                "layout": [t.layout for t in tensors],
                "strides": [str(t.strides) for t in tensors],
                "raw_bytes": [t.raw_bytes for t in tensors],
                "diagnostic": [t.diagnostic for t in tensors],
            },
            schema={
                "tensor": pl.String,
                "shape": pl.String,
                "dtype": pl.String,
                "layout": pl.String,
                "strides": pl.String,
                "raw_bytes": pl.UInt64,
                "diagnostic": pl.String,
            },
        )
        return table, (
            "Restricted CPU checkpoint metadata; values are prepared explicitly. "
            + (
                "Mapped storage available."
                if mapped
                else "Legacy storage reads require explicit preparation."
            ),
        )

    result = read_source(path, options, ImportFormat.CHECKPOINT, read, "")
    assert root is not None
    dataset = replace(
        result.dataset,
        roles=tuple(
            replace(
                info,
                inferred=ColumnRole.IDENTIFIER,
                reason="Tensor locators identify nodes within this checkpoint.",
            )
            if info.name == "tensor"
            else info
            for info in result.dataset.roles or ()
        ),
    )
    catalog = CheckpointCatalog(dataset.source, root, tensors, mapped)
    return replace(
        result, dataset=dataset, checkpoint_catalog=catalog, object_root=root
    )
