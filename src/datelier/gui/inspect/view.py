"""Prepared record cards, linked navigation and virtual supporting-field lists."""

from concurrent.futures import Executor
from dataclasses import replace

from imgui_bundle import imgui

from datelier.core.dataset import Dataset
from datelier.gui.data.table import TableView
from datelier.gui.inspect.controls import InspectControls
from datelier.gui.references.view import ReferenceView
from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.types import InspectSettings, RecordCard
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.plotting.selection import LinkedSelection

CARD_HEIGHT = 240


class InspectView:
    def __init__(self, executor: Executor | None = None) -> None:
        self.controls = InspectControls()
        self.jobs = RecordJobs(executor)
        self.rendered_cards = 0
        self.shown_cards = 0
        self.focused_row: int | None = None
        self.dock_id = 0
        self.card_pixels: dict[int, tuple[float, float]] = {}

    @property
    def settings(self) -> InspectSettings:
        return self.controls.settings

    @settings.setter
    def settings(self, value: InspectSettings) -> None:
        self.controls.settings = value

    def sync(
        self,
        dataset: Dataset | None,
        selection: LinkedSelection,
        default_primary: str | None = None,
    ) -> None:
        if dataset is None:
            self.jobs.abandon()
            return
        self.controls.bind(dataset, default_primary)
        self.jobs.sync(dataset, self.settings, tuple(sorted(selection.row_ids)))
        self.jobs.poll()

    def show(
        self,
        references: ReferenceJobs,
        reference_view: ReferenceView,
        selection: LinkedSelection,
        table: TableView,
    ) -> None:
        self.dock_id = imgui.get_window_dock_id()
        self.controls.show()
        imgui.same_line()
        if imgui.button("Retry Inspect"):
            self.jobs.abandon()
        imgui.text_wrapped(self.jobs.message)
        self.rendered_cards = 0
        self.card_pixels.clear()
        records = self.jobs.active
        if records is None or not len(records.positions):
            imgui.text("Choose records to inspect.")
            return
        if self.settings.gallery:
            if imgui.begin_child("Record gallery", (0, 0)):
                clipper = imgui.ListClipper()
                clipper.begin(len(records.positions), CARD_HEIGHT)
                while clipper.step():
                    for slot in range(clipper.display_start, clipper.display_end):
                        imgui.push_id(slot)
                        if imgui.begin_child(
                            "Card", (0, CARD_HEIGHT - 4), imgui.ChildFlags_.borders
                        ):
                            self._card(
                                slot, references, reference_view, selection, table, True
                            )
                        imgui.end_child()
                        imgui.pop_id()
            imgui.end_child()
        else:
            focus = min(self.settings.focus, len(records.positions) - 1)
            if imgui.button("Previous record"):
                focus = max(0, focus - 1)
            imgui.same_line()
            if imgui.button("Next record"):
                focus = min(len(records.positions) - 1, focus + 1)
            imgui.same_line()
            imgui.text(f"{focus + 1:,}/{len(records.positions):,}")
            self.settings = replace(self.settings, focus=focus)
            self._card(focus, references, reference_view, selection, table, False)

    def _card(
        self,
        slot: int,
        references: ReferenceJobs,
        reference_view: ReferenceView,
        selection: LinkedSelection,
        table: TableView,
        gallery: bool,
    ) -> None:
        records = self.jobs.active
        assert records
        page = self.jobs.get(slot)
        self.rendered_cards += 1
        if page is None:
            imgui.text("Preparing record…")
            return
        card = page.cards[slot - page.start]
        self.shown_cards += 1
        self.focused_row = card.row_id
        if imgui.selectable(
            f"Source row {card.row_id} · table row {card.position + 1}",
            card.row_id in selection.row_ids,
        )[0]:
            selection.choose(
                records.revision, (card.row_id,), toggle=imgui.get_io().key_ctrl
            )
            table.target_row, table.jump = card.position + 1, True
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.card_pixels[card.row_id] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if gallery and imgui.small_button("Focus record"):
            self.settings = replace(self.settings, gallery=False, focus=slot)
        primary = card.primary
        if primary:
            imgui.text_unformatted(primary.name)
            if primary.reference is not None:
                reference_view.cell(
                    references,
                    primary.name,
                    primary.reference,
                    primary.text,
                    extent=80 if gallery else 128,
                )
                resolution, preview = references.get(primary.name, primary.reference)
                if preview and preview.text:
                    imgui.text_wrapped(preview.description)
                    if imgui.begin_child("Text excerpt", (0, 60 if gallery else 110)):
                        imgui.text_wrapped(preview.text)
                    imgui.end_child()
                elif preview and preview.message:
                    imgui.text_wrapped(preview.message)
                elif resolution and resolution.message:
                    imgui.text_wrapped(resolution.message)
            else:
                if imgui.begin_child("Primary value", (0, 70 if gallery else 110)):
                    imgui.text_wrapped(primary.text)
                imgui.end_child()
            if primary.truncated:
                imgui.text("Primary value truncated at 4096 characters.")
        self._fields(card, 72 if gallery else 0)

    def _fields(self, card: RecordCard, height: int) -> None:
        if imgui.begin_child("Supporting values", (0, height)):
            clipper = imgui.ListClipper()
            clipper.begin(len(card.fields))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    field = card.fields[index]
                    text = (
                        field.text.replace("\r", "\\r")
                        .replace("\n", "\\n")
                        .replace("\t", "\\t")
                    )
                    imgui.text_unformatted(
                        f"{field.name}: {text}"
                        + ("… (truncated)" if field.truncated else "")
                    )
        imgui.end_child()

    def close(self) -> None:
        self.jobs.close()
        self.card_pixels.clear()
