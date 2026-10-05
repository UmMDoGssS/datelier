"""Transactional operation history; failed candidates never alter active state."""

from dataclasses import dataclass

from datelier.core.dataset import Dataset
from datelier.pipeline.operations import Operation, OperationFailure, apply_operation


def replay(source: Dataset, operations: tuple[Operation, ...]) -> Dataset:
    result = source
    for operation in operations:
        result = apply_operation(result, operation)
    return result


@dataclass(frozen=True)
class Pipeline:
    source: Dataset
    current: Dataset
    history: tuple[Operation, ...] = ()
    cursor: int = 0

    @classmethod
    def start(cls, source: Dataset) -> Pipeline:
        return cls(source, source)

    @property
    def operations(self) -> tuple[Operation, ...]:
        return self.history[: self.cursor]

    @property
    def can_undo(self) -> bool:
        return self.cursor > 0

    @property
    def can_redo(self) -> bool:
        return self.cursor < len(self.history)

    def apply(self, operation: Operation) -> Pipeline:
        result = apply_operation(self.current, operation)
        history = (*self.operations, operation)
        return Pipeline(self.source, result, history, len(history))

    def undo(self) -> Pipeline:
        if not self.can_undo:
            raise OperationFailure("Nothing to undo")
        result = replay(self.source, self.history[: self.cursor - 1])
        # Even undo to the unedited source publishes a fresh revision.
        result = result.with_rows(result.table, result.row_ids)
        return Pipeline(self.source, result, self.history, self.cursor - 1)

    def redo(self) -> Pipeline:
        if not self.can_redo:
            raise OperationFailure("Nothing to redo")
        result = apply_operation(self.current, self.history[self.cursor])
        return Pipeline(self.source, result, self.history, self.cursor + 1)
