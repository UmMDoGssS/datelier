"""Related tabular option forms receive only their own format's drafts."""

from datelier.application.imports.tabular import (
    DelimitedDraft,
    JsonDraft,
    ParquetDraft,
    XmlDraft,
)
from datelier.gui.components.fields import BooleanField, IntegerField, TextField
from datelier.gui.sources.imports.base import OptionForm


class DelimitedForm(OptionForm):
    description = (
        "Importing replaces this tab's operation pipeline after successful loading."
    )

    def __init__(self, model: DelimitedDraft) -> None:
        super().__init__(
            "delimited",
            (
                TextField(
                    "separator",
                    "Delimiter (\\t = tab)",
                    lambda: model.separator,
                    lambda v: setattr(model, "separator", v),
                ),
                TextField(
                    "quote",
                    "Quote (empty = none)",
                    lambda: model.quote,
                    lambda v: setattr(model, "quote", v),
                ),
                BooleanField(
                    "header",
                    "First record is a header",
                    lambda: model.header,
                    lambda v: setattr(model, "header", v),
                ),
                BooleanField(
                    "text",
                    "Read columns as text",
                    lambda: model.text_only,
                    lambda v: setattr(model, "text_only", v),
                ),
                BooleanField(
                    "dates",
                    "Parse ISO dates",
                    lambda: model.dates,
                    lambda v: setattr(model, "dates", v),
                ),
                IntegerField(
                    "infer",
                    "Infer rows (0 = all)",
                    lambda: model.infer_rows,
                    lambda v: setattr(model, "infer_rows", v),
                ),
                IntegerField(
                    "skip",
                    "Skip records",
                    lambda: model.skip_rows,
                    lambda v: setattr(model, "skip_rows", v),
                ),
                TextField(
                    "nulls",
                    "Null tokens (one per line)",
                    lambda: model.null_tokens,
                    lambda v: setattr(model, "null_tokens", v),
                    True,
                ),
            ),
        )


class JsonForm(OptionForm):
    description = (
        "Record objects retain typed nested columns. Other JSON shapes can open "
        "as a hierarchy."
    )

    def __init__(self, model: JsonDraft) -> None:
        super().__init__(
            "json",
            (
                BooleanField(
                    "text",
                    "Read columns as text",
                    lambda: model.text_only,
                    lambda v: setattr(model, "text_only", v),
                ),
            ),
        )


class ParquetForm(OptionForm):
    description = (
        "Stored types are preserved. Exclude nested Parquet columns before importing."
    )

    def __init__(self, model: ParquetDraft) -> None:
        super().__init__(
            "parquet",
            (
                TextField(
                    "columns",
                    "Column names (one per line; empty = all)",
                    lambda: model.columns,
                    lambda v: setattr(model, "columns", v),
                    True,
                ),
            ),
        )


class XmlForm(OptionForm):
    description = (
        "Record path is relative to the root: ./* for children, .//row for descendants."
    )

    def __init__(self, model: XmlDraft) -> None:
        super().__init__(
            "xml",
            (
                TextField(
                    "record",
                    "Record path",
                    lambda: model.path,
                    lambda v: setattr(model, "path", v),
                ),
                TextField(
                    "namespaces",
                    "Namespaces (prefix=URI per line)",
                    lambda: model.namespaces,
                    lambda v: setattr(model, "namespaces", v),
                    True,
                ),
                BooleanField(
                    "attributes",
                    "Include attributes",
                    lambda: model.attributes,
                    lambda v: setattr(model, "attributes", v),
                ),
                BooleanField(
                    "strip",
                    "Trim text whitespace",
                    lambda: model.strip,
                    lambda v: setattr(model, "strip", v),
                ),
                BooleanField(
                    "text",
                    "Read columns as text",
                    lambda: model.text_only,
                    lambda v: setattr(model, "text_only", v),
                ),
                BooleanField(
                    "dates",
                    "Parse ISO dates",
                    lambda: model.dates,
                    lambda v: setattr(model, "dates", v),
                ),
                TextField(
                    "nulls",
                    "Null tokens (one per line)",
                    lambda: model.null_tokens,
                    lambda v: setattr(model, "null_tokens", v),
                    True,
                ),
            ),
        )
