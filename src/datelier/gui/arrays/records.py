"""Linked mapped-record identity, supporting values and explicit payload preview."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class ArrayRecords:
    def __init__(self, executor: Executor | None = None) -> None:
        self.fields = RecordJobs(executor)
        self.source_index: int | None = None
        self.channel = 0
        self.prepare_pixel = (0.0, 0.0)
        self.next_pixel = (0.0, 0.0)

    def sync(self, view: FileSession) -> None:
        active = view.loader.active
        if active is None or not isinstance(active.imported.options, ArrayOptions):
            self.fields.abandon()
            self.source_index = None
            return
        if active.imported.options.mapping is None:
            return
        records = view.inspect.jobs.active
        chosen: int | None = None
        if view.selection.row_ids:
            chosen = min(view.selection.row_ids)
        elif records is not None and len(records.row_ids):
            focus = min(view.inspect.settings.focus, len(records.row_ids) - 1)
            chosen = int(records.row_ids[focus])
        self.source_index = chosen
        self.fields.sync(
            active.dataset,
            InspectSettings(
                mode=RecordMode.SELECTION,
                count=1,
                supporting=tuple(active.dataset.table.columns),
            ),
            (chosen,) if chosen is not None else (),
        )
        self.fields.poll()

    def show(self, view: FileSession) -> None:
        active, catalog = view.loader.active, view.arrays.catalog
        if active is None or catalog is None:
            return
        options = active.imported.options
        assert isinstance(options, ArrayOptions) and options.mapping is not None
        mapping = options.mapping
        imgui.text_wrapped(
            f"{mapping.member} · {mapping.layout} · record axis {mapping.record_axis}"
        )
        records = view.inspect.jobs.active
        ready = records is not None and len(records.row_ids) > 0
        focus = (
            min(view.inspect.settings.focus, len(records.row_ids) - 1)
            if ready and records is not None
            else 0
        )
        imgui.begin_disabled(not ready)
        if imgui.button("Previous mapped record") and records is not None:
            focus = max(0, focus - 1)
            view.selection.choose(
                active.dataset.revision, [int(records.row_ids[focus])]
            )
        imgui.same_line()
        if imgui.button("Next mapped record") and records is not None:
            focus = min(len(records.row_ids) - 1, focus + 1)
            view.selection.choose(
                active.dataset.revision, [int(records.row_ids[focus])]
            )
        self.next_pixel = _pixel()
        imgui.end_disabled()
        if ready:
            view.inspect.settings = replace(view.inspect.settings, focus=focus)
        index = self.source_index
        if index is None:
            imgui.text("Choose a table row or Inspect record to preview its payload.")
            return
        imgui.text(f"Source record {index} · original axis {mapping.record_axis} index")
        page = self.fields.get(0)
        card = page.cards[0] if page is not None and page.cards else None
        imgui.text(
            f"Current table row {card.position + 1}"
            if card is not None and card.row_id == index
            else "Preparing supporting fields…"
        )
        if imgui.begin_child("Record supporting values", (0, 90)):
            if card is not None and card.row_id == index:
                clipper = imgui.ListClipper()
                clipper.begin(len(card.fields))
                while clipper.step():
                    for position in range(clipper.display_start, clipper.display_end):
                        field = card.fields[position]
                        text = field.text.replace("\n", "\\n").replace("\r", "\\r")
                        imgui.text_unformatted(f"{field.name}: {text}")
        imgui.end_child()
        if mapping.channel_axis is not None:
            size = catalog.member(mapping.member).shape[mapping.channel_axis]
            imgui.push_item_width(100)
            _, self.channel = imgui.input_int(
                f"Channel (0–{max(0, size - 1)})", self.channel
            )
            imgui.pop_item_width()
            imgui.text_wrapped("Image channels are shown as numeric spatial planes.")
        try:
            configured = mapping.slice_settings(catalog, index, channel=self.channel)
        except ValueError as error:
            imgui.text_wrapped(str(error))
            return
        previous = view.arrays.settings
        if previous.member == configured.member and previous.axes == configured.axes:
            configured = replace(
                configured,
                starts=previous.starts,
                counts=previous.counts,
                field=previous.field,
                component=previous.component,
                value_range=previous.value_range,
                colormap=previous.colormap,
            )
        starts = list(configured.starts)
        counts = list(configured.counts)
        imgui.push_item_width(100)
        for i, axis in enumerate(configured.axes):
            _, starts[i] = imgui.input_int(
                f"Record axis {axis} window start", starts[i]
            )
            _, counts[i] = imgui.input_int(
                f"Record axis {axis} window count", counts[i]
            )
        imgui.pop_item_width()
        view.arrays.settings = replace(
            configured, starts=tuple(starts), counts=tuple(counts)
        )
        if imgui.button("Prepare record payload"):
            try:
                view.arrays.request(view.arrays.settings)
            except ValueError as error:
                view.arrays.message = str(error)
        self.prepare_pixel = _pixel()
        imgui.text_wrapped(view.arrays.message)
        view.array_view.show_prepared(view)

    def close(self) -> None:
        self.fields.close()


def _pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
