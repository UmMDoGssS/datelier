"""Selection operation forms, sharing explicit reversible commands."""

from collections.abc import Callable

from datelier.application.tabular import (
    ColumnChoice,
    scalar_input,
)
from datelier.gui.components.inputs import (
    BooleanField,
    ChoiceField,
    TextField,
)
from datelier.gui.context.transforms.base import OperationForm
from datelier.pipeline import (
    Comparison,
    Filter,
    Operation,
    SelectColumns,
    Sort,
)
from datelier.pipeline.editing import DatasetEditor


class SortForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.descending, self.nulls_last = False, True
        super().__init__(
            "Sort",
            choices,
            editor,
            (
                BooleanField(
                    "descending",
                    "Descending",
                    lambda: self.descending,
                    lambda value: setattr(self, "descending", value),
                ),
                BooleanField(
                    "nulls",
                    "Nulls last",
                    lambda: self.nulls_last,
                    lambda value: setattr(self, "nulls_last", value),
                ),
            ),
            multi=True,
        )

    def operation(self) -> Operation:
        return Sort(self.selected, self.descending, self.nulls_last)


class FilterForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.comparison, self.value = Comparison.EQ, ""
        super().__init__(
            "Filter",
            choices,
            editor,
            (
                ChoiceField(
                    "comparison",
                    "Comparison",
                    tuple(Comparison),
                    lambda: self.comparison,
                    lambda value: setattr(self, "comparison", value),
                ),
                TextField(
                    "value",
                    "Value",
                    lambda: self.value,
                    lambda value: setattr(self, "value", value),
                ),
            ),
        )

    def operation(self) -> Operation:
        return Filter(self.column, self.comparison, scalar_input(self.value))


class ColumnsForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        super().__init__("Keep columns", choices, editor, (), multi=True)

    def operation(self) -> Operation:
        return SelectColumns(self.selected)
