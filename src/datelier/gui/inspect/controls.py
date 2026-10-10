"""Per-view record and arbitrary supporting-field choices."""

from dataclasses import dataclass, field, replace

from imgui_bundle import imgui

from datelier.application.columns import ColumnChoice, MultiSelection
from datelier.core.column_roles import REFERENCE_ROLES, ColumnRole
from datelier.core.dataset import Dataset
from datelier.gui.components.columns import ColumnPicker, SingleColumnPicker
from datelier.inspection.records.types import InspectSettings, RecordMode


@dataclass
class InspectControls:
    settings: InspectSettings = InspectSettings()
    columns: tuple[str, ...] = ()
    primary_picker: SingleColumnPicker = field(
        default_factory=lambda: SingleColumnPicker("Primary field")
    )
    supporting_picker: ColumnPicker = field(
        default_factory=lambda: ColumnPicker(
            "Supporting fields", MultiSelection(catalog_order=True)
        )
    )

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
                _, primary = self.primary_picker.choose(self.columns, primary)

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
        supporting = self.supporting_picker.show(
            tuple(ColumnChoice(n) for n in self.columns),
            self.settings.supporting or (),
            caption=f"Supporting fields ({len(self.settings.supporting or ())})",
            bulk_label="All fields",
        )
        self.settings = replace(self.settings, supporting=supporting)
