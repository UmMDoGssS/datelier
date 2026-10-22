"""Replayable operations and transactional undo/redo against an immutable source.

Transforms operate on Polars tables while carrying stable source-row IDs.
Pipeline candidates publish only after successful preparation; failed edits
retain the active table and history. A new edit after undo discards the redo
branch. Role overrides participate in the same saved history as data edits.
Derived columns use the constrained expression grammar, never Python execution.
"""

from datelier.pipeline.history import Pipeline as Pipeline
from datelier.pipeline.history import replay as replay
from datelier.pipeline.operations import Comparison as Comparison
from datelier.pipeline.operations import Filter as Filter
from datelier.pipeline.operations import Operation as Operation
from datelier.pipeline.operations import OperationFailure as OperationFailure
from datelier.pipeline.operations import SelectColumns as SelectColumns
from datelier.pipeline.operations import SetColumnRole as SetColumnRole
from datelier.pipeline.operations import Sort as Sort
from datelier.pipeline.operations import apply_operation as apply_operation
