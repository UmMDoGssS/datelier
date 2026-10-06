"""Explicit mappings use existing schema metadata; Apply submits preparation."""

from dataclasses import dataclass, replace
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.profiles.colors import profile_color
from datelier.gui.widgets.fields import combo
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)


@dataclass
class ComparisonControls:
    draft: ComparisonSettings = ComparisonSettings()
    bound: ComparisonSettings | None = None
    apply_pixel: tuple[float, float] = (0, 0)

    def bind(self, recipe: ComparisonSettings) -> None:
        if self.bound != recipe:
            self.bound = self.draft = recipe

    def show(self, editor: EditorSession) -> bool:
        imgui.text_wrapped(
            "Map one column per file. Use Numeric or Categorical roles; "
            "adjust roles in Schema when needed."
        )
        mappings = {s.file_id: s for s in self.draft.sources}
        if imgui.collapsing_header("File mappings", imgui.TreeNodeFlags_.default_open):
            for file in editor.file_sessions:
                imgui.push_id(file.identity)
                name = (Path(file.controls.path).name or "Welcome").replace(
                    "##", "#\u200b#"
                )
                if file.view_name:
                    name += " · " + file.view_name
                mapping = mappings.get(file.identity)
                picked, enabled = imgui.checkbox(name, mapping is not None)
                columns = (
                    [role.name for role in file.loader.active.dataset.roles or ()]
                    if file.loader.active
                    else []
                )
                if picked:
                    if enabled and columns:
                        mapping = ComparisonSource(file.identity, columns[0])
                    elif not enabled:
                        mapping = None
                if mapping is not None:
                    choices = (
                        columns
                        if mapping.column in columns
                        else [mapping.column, *columns]
                    )
                    if choices:
                        _, index = combo(
                            "Column", choices.index(mapping.column), choices
                        )
                        mapping = replace(mapping, column=choices[index])
                    _, label = imgui.input_text("Label", mapping.label)
                    default = profile_color(file.identity)
                    rgba = mapping.color or (default.x, default.y, default.z, default.w)
                    _, color = imgui.color_edit4("Color", rgba)
                    mapping = replace(
                        mapping,
                        label=label,
                        color=(color[0], color[1], color[2], color[3]),
                    )
                    mappings[file.identity] = mapping
                else:
                    mappings.pop(file.identity, None)
                if not columns:
                    imgui.text_disabled("Open or recover this file to choose a column.")
                imgui.pop_id()
        _, bins = imgui.slider_int("Shared bins", self.draft.bins, 1, 100)
        _, top = imgui.slider_int("Top categories", self.draft.category_limit, 1, 100)
        choices = list(Normalization)
        _, index = combo(
            "Normalization", choices.index(self.draft.normalization), list(choices)
        )
        self.draft = ComparisonSettings(
            tuple(
                mappings[file.identity]
                for file in editor.file_sessions
                if file.identity in mappings
            ),
            bins,
            top,
            choices[index],
        )
        applied = imgui.button("Update comparison")
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.apply_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if self.draft != self.bound:
            imgui.same_line()
            imgui.text("Unapplied changes")
        return applied
