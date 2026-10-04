"""Convert validated scalar records in bounded batches, retaining late fields."""

import json
from collections.abc import Iterable

import polars as pl

BATCH_RECORDS = 4096
type ScalarValue = str | int | float | bool | None


def records_to_table[T: ScalarValue](
    records: Iterable[dict[str, T]], *, as_text: bool = False
) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    batch: list[dict[str, ScalarValue]] = []
    leading_empty: int = 0

    def empty(count: int, name: str) -> pl.DataFrame:
        return pl.select(pl.repeat(None, count).alias(name))

    def flush() -> None:
        nonlocal leading_empty
        if not any(batch):
            if frames:
                frames.append(empty(len(batch), frames[0].columns[0]))
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

    for row in records:
        batch.append(
            {
                key: value
                if not as_text or isinstance(value, str) or value is None
                else json.dumps(value)
                for key, value in row.items()
            }
        )
        if len(batch) == BATCH_RECORDS:
            flush()
    if batch:
        flush()
    if not frames:
        raise ValueError("Records have no fields; empty input has no tabular schema.")
    table = pl.concat(frames, how="diagonal_relaxed")
    return table.cast(pl.String) if as_text else table
