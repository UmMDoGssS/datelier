"""Object, array and checkpoint metadata-first import forms."""

from datelier.application.imports.structured import (
    ArrayDraft,
    CheckpointDraft,
    ObjectDraft,
)
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.sources.imports.base import OptionForm


class ObjectForm(OptionForm):
    description = (
        "Keep the source hierarchy and open compatible record arrays as "
        "independent table views."
    )

    def __init__(self, model: ObjectDraft) -> None:
        super().__init__(
            "object",
            (
                ChoiceField(
                    "syntax",
                    "Object syntax",
                    ("", "json", "toml"),
                    lambda: model.syntax,
                    lambda v: setattr(model, "syntax", v),
                    ("Automatic", "JSON", "TOML"),
                ),
                BooleanField(
                    "text",
                    "Read record columns as text",
                    lambda: model.text_only,
                    lambda v: setattr(model, "text_only", v),
                ),
            ),
        )


class ArrayForm(OptionForm):
    description = (
        "Matching first dimensions open as records with scalar values and lazy "
        "array cells. Other sources open as member metadata."
    )

    def __init__(self, model: ArrayDraft) -> None:
        super().__init__(
            "array",
            (
                ChoiceField(
                    "container",
                    "Array container",
                    (None, False, True),
                    lambda: model.archive,
                    lambda v: setattr(model, "archive", v),
                    ("Automatic", "NPY", "NPZ"),
                ),
                IntegerField(
                    "header",
                    "Maximum header bytes",
                    lambda: model.header_bytes,
                    lambda v: setattr(model, "header_bytes", v),
                    1,
                    16 * 1024 * 1024,
                ),
                BooleanField(
                    "records",
                    "Aligned NPZ members as records",
                    lambda: model.record_table,
                    lambda v: setattr(model, "record_table", v),
                ),
            ),
        )


class CheckpointForm(OptionForm):
    description = (
        "Optional CPU checkpoint inspection opens metadata first; prepare "
        "tensor values explicitly."
    )

    def __init__(self, model: CheckpointDraft) -> None:
        super().__init__(
            "checkpoint",
            (
                IntegerField(
                    "nodes",
                    "Maximum metadata nodes",
                    lambda: model.nodes,
                    lambda v: setattr(model, "nodes", v),
                    1,
                    1_000_000,
                ),
                IntegerField(
                    "depth",
                    "Maximum metadata depth",
                    lambda: model.depth,
                    lambda v: setattr(model, "depth", v),
                    1,
                    256,
                ),
            ),
        )
