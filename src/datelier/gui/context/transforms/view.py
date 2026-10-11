"""View operation forms, sharing explicit reversible commands."""

from collections.abc import Callable

from datelier.application.tabular import (
    ColumnChoice,
)
from datelier.gui.components.actions import JobFeedback, JobSnapshot
from datelier.gui.components.inputs import (
    ChoiceField,
)
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.context.transforms.selection import ColumnsForm, FilterForm, SortForm
from datelier.gui.context.transforms.values import (
    CastForm,
    DerivedForm,
    DropForm,
    FillForm,
    LookupForm,
)
from datelier.pipeline.editing import DatasetEditor

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
