"""Explicit table edits and history controls; all computation runs in workers."""

import json
from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.editing import DatasetEditor, HistoryAction
from datelier.expressions import HELP
from datelier.gui_transforms import TransformControls
from datelier.gui_values import scalar_input
from datelier.operations import (
    Comparison,
    Filter,
    SelectColumns,
    Sort,
    describe_operation,
)
from datelier.transform_types import DerivedColumn


@dataclass
class OperationControls:
    transforms: TransformControls = field(default_factory=TransformControls)
    column: str = ""
    descending: bool = False
    comparison: int = 0
    value: str = ""
    selected: str = ""
    derived_expanded: bool = False
    derived_name: str = ""
    expression: str = ""
    replace_existing: bool = False
    error: str = ""

    def show(self, editor: DatasetEditor, *, loading: bool) -> None:
        imgui.push_item_width(135)
        pipeline = editor.pipeline
        imgui.text_wrapped(editor.message)
        if self.error:
            imgui.text_wrapped(self.error)
        if editor.busy and imgui.button("Abandon edit"):
            editor.abandon()
        imgui.begin_disabled(editor.busy or loading or pipeline is None)
        try:
            imgui.begin_disabled(pipeline is None or not pipeline.can_undo)
            if imgui.button("Undo"):
                editor.request(HistoryAction.UNDO)
            imgui.end_disabled()
            imgui.same_line()
            imgui.begin_disabled(pipeline is None or not pipeline.can_redo)
            if imgui.button("Redo"):
                editor.request(HistoryAction.REDO)
            imgui.end_disabled()
            _, self.column = imgui.input_text("Column", self.column)
            _, self.descending = imgui.checkbox("Descending", self.descending)
            if imgui.button("Sort column"):
                editor.request(Sort((self.column,), self.descending))
            _, self.comparison = imgui.combo(
                "Comparison", self.comparison, [item.value for item in Comparison]
            )
            _, self.value = imgui.input_text("Filter value", self.value)
            imgui.text_wrapped(
                'Values accept numbers, true/false, or text. Quote text like "1".'
            )
            if imgui.button("Filter rows"):
                editor.request(
                    Filter(
                        self.column,
                        list(Comparison)[self.comparison],
                        scalar_input(self.value),
                    )
                )
            _, self.selected = imgui.input_text("Columns to keep", self.selected)
            imgui.text_wrapped(
                'Column selection is a JSON list, e.g. ["name", "value"].'
            )
            if imgui.button("Keep columns"):
                names = json.loads(self.selected)
                if not isinstance(names, list) or not all(
                    isinstance(n, str) for n in names
                ):
                    raise ValueError("Enter a JSON list of column names")
                editor.request(SelectColumns(tuple(names)))
            self.transforms.show(editor, self.column)
            imgui.set_next_item_open(self.derived_expanded, imgui.Cond_.once)
            self.derived_expanded = imgui.collapsing_header("Derived columns")
            if self.derived_expanded:
                imgui.text_wrapped(HELP)
                _, self.derived_name = imgui.input_text("New column", self.derived_name)
                _, self.expression = imgui.input_text("Expression", self.expression)
                _, self.replace_existing = imgui.checkbox(
                    "Replace existing column", self.replace_existing
                )
                if imgui.button("Derive column"):
                    editor.request(
                        DerivedColumn(
                            self.derived_name, self.expression, self.replace_existing
                        )
                    )
            self.error = ""
        except ValueError as error:
            self.error = str(error)
        finally:
            imgui.end_disabled()
        if pipeline:
            imgui.separator()
            imgui.text(f"History: {pipeline.cursor} of {len(pipeline.history)} applied")
            for index, operation in enumerate(pipeline.history):
                suffix = " (undone)" if index >= pipeline.cursor else ""
                imgui.text_wrapped(
                    f"{index + 1}. {describe_operation(operation)}{suffix}"
                )
        imgui.pop_item_width()
