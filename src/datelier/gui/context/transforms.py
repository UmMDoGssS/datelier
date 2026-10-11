"""Related reversible operation forms share typed selectors and explicit commands."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from datelier.application.tabular import (
    ColumnChoice,
    MultiSelection,
    SingleSelection,
    lookup_entries,
    scalar_input,
)
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import BooleanField, ChoiceField, TextField
from datelier.pipeline.editing import DatasetEditor
from datelier.pipeline.operations import (
    Comparison,
    Filter,
    Operation,
    SelectColumns,
    Sort,
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


class OperationForm(Container, ABC):
    def __init__(
        self,
        key: str,
        choices: Callable[[], tuple[ColumnChoice, ...]],
        editor: DatasetEditor,
        fields: tuple[Component, ...],
        multi: bool = False,
        requires_column: bool = True,
    ) -> None:
        self.selected: tuple[str, ...] = ()
        self.editor = editor
        children: tuple[Component, ...] = (
            (
                ColumnPicker(
                    "columns",
                    "Columns" if multi else "Column",
                    choices,
                    lambda: self.selected,
                    lambda names: setattr(self, "selected", names),
                    MultiSelection() if multi else SingleSelection(),
                ),
            )
            if requires_column
            else ()
        )
        super().__init__(
            key,
            (
                *children,
                *fields,
                CommandButton(
                    "apply",
                    "Apply",
                    self.apply,
                    lambda: editor.pipeline is not None and not editor.busy,
                ),
            ),
        )

    @property
    def column(self) -> str:
        if not self.selected:
            raise ValueError("Choose a column")
        return self.selected[0]

    @abstractmethod
    def operation(self) -> Operation: ...

    def apply(self) -> None:
        self.editor.request(self.operation())


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


FORMS = (
    SortForm,
    FilterForm,
    ColumnsForm,
    CastForm,
    FillForm,
    DropForm,
    LookupForm,
    DerivedForm,
)


class TransformSettings(Container):
    def __init__(
        self, choices: Callable[[], tuple[ColumnChoice, ...]], editor: DatasetEditor
    ) -> None:
        self.forms = tuple(form(choices, editor) for form in FORMS)
        self.selected = 0
        self.selector = ChoiceField(
            "operation",
            "Operation",
            tuple(range(len(self.forms))),
            lambda: self.selected,
            lambda value: setattr(self, "selected", value),
            tuple(form.key for form in self.forms),
        )
        self.feedback = JobFeedback(
            "edit", lambda: JobSnapshot(editor.message, editor.busy), editor.abandon
        )
        super().__init__("transforms", ())

    def render(self, frame: FrameContext) -> None:
        self.children = (self.selector, self.forms[self.selected], self.feedback)
        super().render(frame)
