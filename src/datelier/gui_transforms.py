"""Type, missing-value, and lookup controls rendered within the edit panel."""

import json
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.editing import DatasetEditor
from datelier.gui_values import scalar_input
from datelier.scalars import Scalar
from datelier.transform_types import (
    CastColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)


def lookup_entries(text: str) -> tuple[tuple[Scalar, Scalar], ...]:
    values = json.loads(text)
    if not isinstance(values, list):
        raise ValueError("Use a JSON list of [key, value] pairs")
    result: list[tuple[Scalar, Scalar]] = []
    for pair in values:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each lookup entry needs a key and value")
        if not all(
            value is None or isinstance(value, (str, int, float, bool))
            for value in pair
        ):
            raise ValueError("Lookup keys and values must be scalar")
        result.append((pair[0], pair[1]))
    return tuple(result)


@dataclass
class TransformControls:
    expanded: bool = False
    dtype: int = 0
    strict: bool = True
    replacement: str = "0"
    nonfinite: bool = False
    mapping: str = ""
    unmatched: int = 0

    def show(self, editor: DatasetEditor, column: str) -> None:
        imgui.set_next_item_open(self.expanded, imgui.Cond_.once)
        self.expanded = imgui.collapsing_header("Types, missing values and mappings")
        if not self.expanded:
            return
        _, self.dtype = imgui.combo(
            "Target type", self.dtype, [item.value for item in TargetType]
        )
        dtype = list(TargetType)[self.dtype]
        _, self.strict = imgui.checkbox("Reject invalid casts", self.strict)
        if imgui.button("Cast column"):
            editor.request(CastColumn(column, dtype, self.strict))
        _, self.nonfinite = imgui.checkbox("Treat nonfinite as missing", self.nonfinite)
        _, self.replacement = imgui.input_text("Replacement", self.replacement)
        if imgui.button("Fill missing"):
            editor.request(
                FillMissing(column, scalar_input(self.replacement), self.nonfinite)
            )
        imgui.same_line()
        if imgui.button("Drop missing rows"):
            editor.request(DropMissing((column,), self.nonfinite))
        _, self.mapping = imgui.input_text("Lookup pairs", self.mapping)
        imgui.text_wrapped(
            'Enter pairs like [["old", "new"], ["other", "next"]]. '
            "Uses the target type above."
        )
        _, self.unmatched = imgui.combo(
            "Unmatched keys", self.unmatched, [item.value for item in Unmatched]
        )
        if imgui.button("Apply lookup"):
            editor.request(
                Lookup(
                    column,
                    lookup_entries(self.mapping),
                    dtype,
                    list(Unmatched)[self.unmatched],
                )
            )
