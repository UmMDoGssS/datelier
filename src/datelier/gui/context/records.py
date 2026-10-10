"""Inspect collection controls share the column and field families."""

from dataclasses import replace

from datelier.application.columns import MultiSelection, SingleSelection
from datelier.application.records import RecordController
from datelier.gui.components.base import Container
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.fields import BooleanField, ChoiceField, IntegerField
from datelier.gui.components.groups import Conditional
from datelier.inspection.records.types import RecordMode


class RecordSettings(Container):
    def __init__(self, model: RecordController) -> None:
        super().__init__(
            "records",
            (
                ChoiceField(
                    "scope",
                    "Records",
                    tuple(RecordMode),
                    lambda: model.settings.mode,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, mode=value)
                    ),
                ),
                ColumnPicker(
                    "primary",
                    "Primary content",
                    lambda: model.choices,
                    lambda: (model.settings.primary,) if model.settings.primary else (),
                    lambda names: setattr(
                        model,
                        "settings",
                        replace(model.settings, primary=names[0] if names else None),
                    ),
                    SingleSelection(),
                ),
                ColumnPicker(
                    "supporting",
                    "Supporting fields",
                    lambda: model.choices,
                    lambda: model.settings.supporting or (),
                    lambda names: setattr(
                        model, "settings", replace(model.settings, supporting=names)
                    ),
                    MultiSelection(),
                ),
                Conditional(
                    "mapped-payload",
                    lambda: model.has_mapped_payload,
                    (
                        BooleanField(
                            "payload",
                            "Inspect mapped payload",
                            lambda: model.settings.mapped_payload is not False,
                            lambda value: setattr(
                                model,
                                "settings",
                                replace(model.settings, mapped_payload=value),
                            ),
                        ),
                    ),
                ),
                Conditional(
                    "text-elements",
                    lambda: model.text_list,
                    (
                        BooleanField(
                            "text",
                            "Inspect text list elements",
                            lambda: model.settings.text_elements,
                            lambda value: setattr(
                                model,
                                "settings",
                                replace(
                                    model.settings,
                                    text_elements=value,
                                    mapped_payload=False
                                    if value
                                    else model.settings.mapped_payload,
                                ),
                            ),
                        ),
                    ),
                ),
                IntegerField(
                    "start",
                    "First row (1-based)",
                    lambda: model.settings.start,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, start=value)
                    ),
                    1,
                ),
                IntegerField(
                    "count",
                    "Record count",
                    lambda: model.settings.count,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, count=value)
                    ),
                    1,
                ),
                IntegerField(
                    "seed",
                    "Random seed",
                    lambda: model.settings.seed,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, seed=value)
                    ),
                    0,
                    2**32 - 1,
                ),
                BooleanField(
                    "gallery",
                    "Gallery",
                    lambda: model.settings.gallery,
                    lambda value: setattr(
                        model, "settings", replace(model.settings, gallery=value)
                    ),
                ),
            ),
        )
