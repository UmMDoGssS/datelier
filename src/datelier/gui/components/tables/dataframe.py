"""Prepared Polars frames adapt to the common virtual table contract."""

from collections.abc import Callable

import polars as pl

from datelier.gui.components.tables.base import VirtualTable


class DataFrameTable(VirtualTable):
    def __init__(
        self,
        key: str,
        table: Callable[[], pl.DataFrame | None],
        height: float = 240,
        open_row: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(key, height, open_row)
        self.table = table
        self._table: pl.DataFrame | None = None

    def bind(self) -> tuple[tuple[str, ...], int]:
        self._table = self.table()
        return (
            (tuple(self._table.columns), self._table.height)
            if self._table is not None
            else ((), 0)
        )

    def row(self, index: int) -> tuple[object, ...]:
        return self._table.row(index) if self._table is not None else ()

    def close(self) -> None:
        self._table = None
