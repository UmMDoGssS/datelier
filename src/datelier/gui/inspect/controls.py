"""Per-view record and arbitrary supporting-field choices."""

from dataclasses import dataclass, replace

from imgui_bundle import imgui

from datelier.core.column_roles import REFERENCE_ROLES, ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.records.types import InspectSettings, RecordMode


@dataclass
class InspectControls:
    settings: InspectSettings = InspectSettings()
    columns: tuple[str, ...] = ()
    search: str = ""

    def bind(self, dataset: Dataset, default_primary: str | None = None) -> None:
        columns = tuple(dataset.table.columns)
        if (
            self.columns != columns
            or self.settings.primary not in columns
            or any(n not in columns for n in self.settings.supporting or ())
        ):
            self.columns = columns
            primary = (
                self.settings.primary
                if self.settings.primary in columns
                else default_primary
                if default_primary in columns
                else next(
                    (
                        info.name
                        for info in dataset.roles or ()
                        if info.role in REFERENCE_ROLES
                    ),
                    next(
                        (
                            i.name
                            for i in dataset.roles or ()
                            if i.role == ColumnRole.TEXT
                        ),
                        columns[0] if columns else None,
                    ),
                )
            )
            supporting = tuple(
                n for n in (self.settings.supporting or ()) if n in columns
            )
            if self.settings.supporting is None:
                supporting = tuple(n for n in columns if n != primary)[:4]
            self.settings = replace(
                self.settings, primary=primary, supporting=supporting
            )

    def show(self) -> None:
        settings = self.settings
        _, gallery = imgui.checkbox("Gallery", settings.gallery)
        self.settings = replace(settings, gallery=gallery)
        if imgui.collapsing_header("Inspect settings"):
            modes = list(RecordMode)
            _, mode = imgui.combo(
                "Records", modes.index(settings.mode), [m.value for m in modes]
            )
            _, start = imgui.input_int("First row", settings.start)
            _, count = imgui.input_int("Record count", settings.count)
            _, seed = imgui.input_int("Sample seed", settings.seed)
            primary = settings.primary
            if self.columns:
                _, choice = imgui.combo(
                    "Primary field",
                    self.columns.index(settings.primary or self.columns[0]),
                    list(self.columns),
                )
                primary = self.columns[choice]
            self.settings = replace(
                self.settings,
                mode=modes[mode],
                start=max(1, start),
                count=max(1, count),
                seed=max(0, min(seed, 2**32 - 1)),
                primary=primary,
            )
            imgui.text_wrapped(
                "Ranges use current row positions. Seeded samples use stable "
                "source IDs; linked selection stays in this file."
            )
        if imgui.button(f"Supporting fields ({len(self.settings.supporting or ())})"):
            imgui.open_popup("Supporting columns")
        if imgui.begin_popup("Supporting columns"):
            selected = set(self.settings.supporting or ())
            if imgui.button("All fields"):
                selected = set(self.columns)
            imgui.same_line()
            if imgui.button("Clear fields"):
                selected.clear()
            _, self.search = imgui.input_text("Find field", self.search)
            names = tuple(n for n in self.columns if self.search.lower() in n.lower())
            if imgui.begin_child("Field checklist", (340, 240)):
                clipper = imgui.ListClipper()
                clipper.begin(len(names))
                while clipper.step():
                    for index in range(clipper.display_start, clipper.display_end):
                        name = names[index]
                        changed, checked = imgui.checkbox(name, name in selected)
                        if changed:
                            if checked:
                                selected.add(name)
                            else:
                                selected.discard(name)
            imgui.end_child()
            self.settings = replace(
                self.settings,
                supporting=tuple(n for n in self.columns if n in selected),
            )
            if imgui.button("Done"):
                imgui.close_current_popup()
            imgui.end_popup()
