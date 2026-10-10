"""History content renders replayable operations from the edit controller."""

from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.base import Container
from datelier.gui.components.facts import FactsTable
from datelier.pipeline.editing import DatasetEditor, HistoryAction


class HistoryView(Container):
    def __init__(self, editor: DatasetEditor) -> None:
        def rows() -> tuple[tuple[object, ...], ...]:
            pipeline = editor.pipeline
            return (
                tuple(
                    (
                        i + 1,
                        str(operation),
                        "Applied" if i < pipeline.cursor else "Undone",
                    )
                    for i, operation in enumerate(pipeline.history)
                )
                if pipeline
                else ()
            )

        super().__init__(
            "history",
            (
                CommandButton(
                    "undo",
                    "Undo",
                    lambda: editor.request(HistoryAction.UNDO),
                    lambda: (
                        bool(editor.pipeline and editor.pipeline.can_undo)
                        and not editor.busy
                    ),
                ),
                CommandButton(
                    "redo",
                    "Redo",
                    lambda: editor.request(HistoryAction.REDO),
                    lambda: (
                        bool(editor.pipeline and editor.pipeline.can_redo)
                        and not editor.busy
                    ),
                ),
                JobFeedback(
                    "history-status", lambda: JobSnapshot(editor.message, editor.busy)
                ),
                FactsTable("operations", ("Step", "Operation", "State"), rows, 300),
            ),
        )
