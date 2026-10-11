"""Base operation forms, sharing explicit reversible commands."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from datelier.application.tabular import (
    ColumnChoice,
    MultiSelection,
    SingleSelection,
)
from datelier.gui.components.actions import CommandButton
from datelier.gui.components.inputs import (
    ColumnPicker,
)
from datelier.gui.components.layout import Component, Container
from datelier.pipeline import (
    Operation,
)
from datelier.pipeline.editing import DatasetEditor


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
