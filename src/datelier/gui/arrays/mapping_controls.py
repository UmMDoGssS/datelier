"""Editable array layout drafts; confirmation creates an independent record view."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.arrays.mapping_jobs import MappingJobs
from datelier.inspection.arrays.types import ArrayCatalog

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


def member_combo(catalog: ArrayCatalog, label: str, chosen: str) -> str:
    index = catalog.indices.get(chosen, 0)
    if imgui.begin_combo(label, catalog.members[index].name[:256].replace("##", "# #")):
        clipper = imgui.ListClipper()
        clipper.begin(len(catalog.members))
        while clipper.step():
            for item in range(clipper.display_start, clipper.display_end):
                name = catalog.members[item].name
                display = name[:256].replace("##", "# #")
                if imgui.selectable(f"{display}###member{item}", index == item)[0]:
                    index = item
        imgui.end_combo()
    return catalog.members[index].name


class MappingControls:
    def __init__(self, executor: Executor | None = None) -> None:
        self.jobs = MappingJobs(executor)
        self.catalog: ArrayCatalog | None = None
        self.draft: ArrayRecordMapping | None = None
        self.opened = False
        self.support_member = ""
        self.support_page = 0
        self.confirm_pixel = (0.0, 0.0)
        self.configure_pixel = (0.0, 0.0)
        self.message = ""

    def bind(self, catalog: ArrayCatalog | None) -> None:
        if catalog is not self.catalog:
            self.catalog = catalog
            self.jobs.abandon()
            self.draft = None
            self.message = ""
            self.opened = False

    def poll(self) -> None:
        if self.jobs.poll() and self.jobs.active is not None:
            self.draft = self.jobs.active.mapping

    def edit(self, mapping: ArrayRecordMapping) -> None:
        self.jobs.abandon()
        self.draft, self.opened = mapping, True
        self.support_page = 0
        self.message = "Edit this draft and confirm to open its record view."

    def show(self, owner: FileSession) -> None:
        catalog = self.catalog
        if catalog is None or not catalog.members:
            return
        if imgui.button("Configure array records"):
            self.opened = not self.opened
            if self.opened and self.draft is None:
                chosen = owner.arrays.settings.member
                member = (
                    chosen if chosen in catalog.indices else catalog.members[0].name
                )
                self.jobs.request(catalog, member)
        self.configure_pixel = _pixel()
        if not self.opened:
            return
        imgui.text_wrapped(self.jobs.message)
        draft = self.draft
        if draft is None:
            return
        name = member_combo(catalog, "Record payload", draft.member)
        if name != draft.member:
            self.jobs.request(catalog, name)
            self.draft = None
            return
        member = catalog.member(name)
        imgui.text_wrapped(f"{member.shape} · {member.dtype}")
        if not member.shape:
            imgui.text("Scalar arrays have no record axis.")
            return
        _, record = imgui.combo(
            "Record axis", draft.record_axis, [str(i) for i in range(len(member.shape))]
        )
        layouts = list(ArrayLayout)
        changed, layout_index = imgui.combo(
            "Record layout",
            layouts.index(draft.layout),
            [layout.value for layout in layouts],
        )
        layout = layouts[layout_index]
        axes = draft.display_axes
        if changed:
            count = 1 if layout == ArrayLayout.AUDIO else 2
            axes = tuple(i for i in range(len(member.shape)) if i != record)[-count:]
        channel = draft.channel_axis
        channel_choices = ["None", *(str(i) for i in range(len(member.shape)))]
        _, channel_index = imgui.combo(
            "Channel axis", 0 if channel is None else channel + 1, channel_choices
        )
        channel = channel_index - 1 if channel_index else None
        configured: list[int] = []
        for i, axis in enumerate(axes):
            _, axis = imgui.combo(
                f"Spatial/sample axis {i + 1}",
                axis,
                [str(j) for j in range(len(member.shape))],
            )
            configured.append(axis)
        fixed = list(draft.fixed or (0,) * len(member.shape))
        imgui.push_item_width(100)
        for i, size in enumerate(member.shape):
            if i not in (record, *configured, channel):
                _, fixed[i] = imgui.input_int(f"Fixed axis {i} (size {size})", fixed[i])
        imgui.pop_item_width()
        draft = replace(
            draft,
            record_axis=record,
            layout=layout,
            display_axes=tuple(configured),
            channel_axis=channel,
            fixed=tuple(fixed),
        )
        self.draft = self._supporting(catalog, draft)
        imgui.text_wrapped(
            "Confirmation loads scalar supporting columns. "
            "Array payloads are prepared only for requested records."
        )
        if imgui.button("Confirm mapping and open records"):
            try:
                owner.record_views.open_array(owner, self.draft)
                self.message = "Preparing aligned scalar records…"
            except ValueError as error:
                self.message = str(error)
        self.confirm_pixel = _pixel()
        imgui.text_wrapped(self.message or owner.record_views.message)

    def _supporting(
        self, catalog: ArrayCatalog, draft: ArrayRecordMapping
    ) -> ArrayRecordMapping:
        supports = list(draft.supporting)
        imgui.separator()
        imgui.text(f"Supporting columns: {len(supports)}")
        self.support_member = member_combo(
            catalog, "Supporting array", self.support_member
        )
        if imgui.small_button("Add supporting column") and len(supports) < 256:
            supports.append(
                SupportingArray(self.support_member, f"value_{len(supports)}")
            )
        if len(supports) > 8:
            _, self.support_page = imgui.slider_int(
                "Supporting page", self.support_page, 0, (len(supports) - 1) // 8
            )
        for index in range(
            self.support_page * 8, min(len(supports), self.support_page * 8 + 8)
        ):
            support = supports[index]
            imgui.push_id(index)
            member = catalog.member(support.member)
            imgui.text_wrapped(f"{support.member} · {member.shape} · {member.dtype}")
            _, column = imgui.input_text("Column name", support.column)
            axis = support.record_axis
            fixed = list(support.fixed or (0,) * len(member.shape))
            if member.shape:
                _, axis = imgui.combo(
                    "Supporting record axis",
                    axis,
                    [str(j) for j in range(len(member.shape))],
                )
                imgui.push_item_width(100)
                for j, size in enumerate(member.shape):
                    if j != axis:
                        _, fixed[j] = imgui.input_int(
                            f"Support axis {j} (size {size})", fixed[j]
                        )
                imgui.pop_item_width()
            fields = list(member.dtype.names or ()) if member.dtype is not None else []
            chosen = support.field
            if fields:
                _, fi = imgui.combo(
                    "Scalar field",
                    fields.index(chosen) + 1
                    if chosen is not None and chosen in fields
                    else 0,
                    ["Raw scalar", *fields],
                )
                chosen = fields[fi - 1] if fi else None
            supports[index] = replace(
                support,
                column=column,
                record_axis=axis,
                fixed=tuple(fixed),
                field=chosen,
            )
            if imgui.small_button("Remove supporting column"):
                supports.pop(index)
                imgui.pop_id()
                break
            imgui.pop_id()
        return replace(draft, supporting=tuple(supports))

    def close(self) -> None:
        self.jobs.close()


def _pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
