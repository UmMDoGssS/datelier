"""Values operation forms, sharing explicit reversible commands."""

from collections.abc import Callable

from datelier.application.tabular import (
    ColumnChoice,
    lookup_entries,
    scalar_input,
)
from datelier.gui.components.inputs import (
    BooleanField,
    ChoiceField,
    TextField,
)
from datelier.gui.context.transforms.base import OperationForm
from datelier.pipeline.editing import DatasetEditor
from datelier.pipeline.operations import (
    Operation,
)
from datelier.pipeline.transforms import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)


class CastForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.dtype, self.strict = TargetType.FLOAT, True
        super().__init__(
            "Cast",
            choices,
            editor,
            (
                ChoiceField(
                    "type",
                    "Target type",
                    tuple(TargetType),
                    lambda: self.dtype,
                    lambda value: setattr(self, "dtype", value),
                ),
                BooleanField(
                    "strict",
                    "Reject invalid casts",
                    lambda: self.strict,
                    lambda value: setattr(self, "strict", value),
                ),
            ),
        )

    def operation(self) -> Operation:
        return CastColumn(self.column, self.dtype, self.strict)


class FillForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.value, self.nonfinite = "0", False
        super().__init__(
            "Fill missing",
            choices,
            editor,
            (
                TextField(
                    "value",
                    "Replacement",
                    lambda: self.value,
                    lambda value: setattr(self, "value", value),
                ),
                BooleanField(
                    "nonfinite",
                    "Treat nonfinite as missing",
                    lambda: self.nonfinite,
                    lambda value: setattr(self, "nonfinite", value),
                ),
            ),
        )

    def operation(self) -> Operation:
        return FillMissing(self.column, scalar_input(self.value), self.nonfinite)


class DropForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.nonfinite = False
        super().__init__(
            "Drop missing",
            choices,
            editor,
            (
                BooleanField(
                    "nonfinite",
                    "Treat nonfinite as missing",
                    lambda: self.nonfinite,
                    lambda value: setattr(self, "nonfinite", value),
                ),
            ),
            multi=True,
        )

    def operation(self) -> Operation:
        return DropMissing(self.selected, self.nonfinite)


class LookupForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.pairs, self.dtype, self.unmatched = "[]", TargetType.TEXT, Unmatched.KEEP
        super().__init__(
            "Lookup",
            choices,
            editor,
            (
                TextField(
                    "pairs",
                    'Pairs: [["old", "new"]]',
                    lambda: self.pairs,
                    lambda value: setattr(self, "pairs", value),
                    multiline=True,
                ),
                ChoiceField(
                    "type",
                    "Target type",
                    tuple(TargetType),
                    lambda: self.dtype,
                    lambda value: setattr(self, "dtype", value),
                ),
                ChoiceField(
                    "unmatched",
                    "Unmatched",
                    tuple(Unmatched),
                    lambda: self.unmatched,
                    lambda value: setattr(self, "unmatched", value),
                ),
            ),
        )

    def operation(self) -> Operation:
        return Lookup(
            self.column, lookup_entries(self.pairs), self.dtype, self.unmatched
        )


class DerivedForm(OperationForm):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.name, self.expression, self.replace = "derived", "", False
        super().__init__(
            "Derived column",
            choices,
            editor,
            (
                TextField(
                    "name",
                    "New column name",
                    lambda: self.name,
                    lambda value: setattr(self, "name", value),
                ),
                TextField(
                    "expression",
                    "Expression",
                    lambda: self.expression,
                    lambda value: setattr(self, "expression", value),
                    multiline=True,
                ),
                BooleanField(
                    "replace",
                    "Replace existing column",
                    lambda: self.replace,
                    lambda value: setattr(self, "replace", value),
                ),
            ),
            requires_column=False,
        )

    def operation(self) -> Operation:
        return DerivedColumn(self.name, self.expression, self.replace)
