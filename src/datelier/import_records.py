"""Convert validated scalar records in bounded batches, retaining late fields."""

import json
from collections.abc import Iterable
from time import sleep

import polars as pl

BATCH_RECORDS = 1024
BATCH_CELLS = 4096
YIELD_CELLS = 256
BLOCK_BATCHES = 32
type ScalarValue = str | int | float | bool | None


def records_to_table[T: ScalarValue](
    records: Iterable[dict[str, T]], *, as_text: bool = False
) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    blocks: list[pl.DataFrame] = []
    batch: list[dict[str, ScalarValue]] = []
    leading_empty: int = 0
    batch_cells = 0
    yield_cells = 0

    def empty(count: int, name: str) -> pl.DataFrame:
        return pl.select(pl.repeat(None, count).alias(name))

    def flush() -> None:
        nonlocal leading_empty
        if not any(batch):
            if frames or blocks:
                first = blocks[0] if blocks else frames[0]
                frames.append(empty(len(batch), first.columns[0]))
            else:
                leading_empty += len(batch)
        else:
            schema = (
                {name: pl.String for row in batch for name in row} if as_text else None
            )
            table = pl.from_dicts(
                batch, schema=schema, infer_schema_length=None, strict=True
            )
            if leading_empty:
                frames.append(empty(leading_empty, table.columns[0]))
                leading_empty = 0
            frames.append(table)
        batch.clear()
        if len(frames) >= BLOCK_BATCHES:
            # Merge a bounded group once, avoiding thousands of tiny per-column
            # chunks without repeatedly copying the accumulated table.
            blocks.append(pl.concat(frames, how="diagonal_relaxed", rechunk=True))
            frames.clear()

    for row in records:
        batch.append(
            {
                key: value
                if not as_text or isinstance(value, str) or value is None
                else json.dumps(value)
                for key, value in row.items()
            }
        )
        batch_cells += max(1, len(row))
        yield_cells += max(1, len(row))
        if len(batch) == BATCH_RECORDS or batch_cells >= BATCH_CELLS:
            flush()
            batch_cells = 0
        if yield_cells >= YIELD_CELLS:
            # Yield the GIL so native GUI callbacks can acquire it promptly.
            sleep(0)
            yield_cells = 0
    if batch:
        flush()
    if not frames and not blocks:
        raise ValueError("Records have no fields; empty input has no tabular schema.")
    table = pl.concat([*blocks, *frames], how="diagonal_relaxed")
    return table.cast(pl.String) if as_text else table
