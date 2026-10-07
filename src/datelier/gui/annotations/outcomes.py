"""Virtual association outcomes and linked record selection from prepared state."""

from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.inspection.annotations.association_types import (
    AssociatedSource,
    PreparedAnnotations,
)
from datelier.inspection.records.types import RecordMode

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


def open_image(owner: FileSession, prepared: PreparedAnnotations, row: int) -> None:
    open_rows(owner, prepared, (row,))


def open_rows(
    owner: FileSession, prepared: PreparedAnnotations, rows: tuple[int, ...]
) -> None:
    active = owner.loader.active
    if active is None or (owner.identity, owner.view_name, active.dataset.revision) != (
        prepared.file_id,
        prepared.view_name,
        prepared.revision,
    ):
        return
    owner.selection.choose(prepared.revision, rows)
    owner.inspect.settings = replace(
        owner.inspect.settings,
        mode=RecordMode.SELECTION,
        gallery=False,
        focus=0,
        primary=prepared.column
        if prepared.column in active.dataset.table.columns
        else owner.inspect.settings.primary,
    )
    owner.exploration.tab = "Inspect"


def outcomes(
    source: AssociatedSource, prepared: PreparedAnnotations, owner: FileSession
) -> None:
    imgui.text_wrapped(
        f"{len(source.images):,} image keys · {len(source.boxes):,} usable boxes · "
        f"{len(source.issues):,} issues"
    )
    if source.error:
        imgui.text_wrapped(source.error)
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
    )
    if imgui.begin_table("Annotation image outcomes", 6, flags, (-1, 170)):
        for name, width in (
            ("Image key", 160),
            ("Status / labels", 145),
            ("Source rows", 100),
            ("Image reference", 200),
            ("Original size", 110),
            ("Diagnostic", 300),
        ):
            imgui.table_setup_column(name, imgui.TableColumnFlags_.width_fixed, width)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(source.images))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                item = source.images[index]
                imgui.push_id(index)
                imgui.table_next_row()
                imgui.table_next_column()
                if item.locator is not None:
                    if imgui.selectable(
                        item.image.key,
                        item.locator.origin.row_id in owner.selection.row_ids,
                    )[0]:
                        open_image(owner, prepared, item.locator.origin.row_id)
                else:
                    imgui.text_unformatted(item.image.key)
                for cell in (
                    f"{item.status} / {item.image.label_status}",
                    ", ".join(map(str, item.candidates)),
                    item.image.reference,
                    "×".join(map(str, item.dimensions)) if item.dimensions else "—",
                    "; ".join(item.diagnostics),
                ):
                    imgui.table_next_column()
                    imgui.text_unformatted(cell)
                imgui.pop_id()
        imgui.end_table()
    if source.boxes and imgui.tree_node("Original and pixel boxes"):
        box_records(source, owner)
        imgui.tree_pop()
    if source.issues and imgui.tree_node("Annotation issues and original records"):
        if imgui.begin_table("Annotation issues", 5, flags, (-1, 160)):
            for name in ("Image key", "File", "Location", "Diagnostic", "Original"):
                imgui.table_setup_column(name, imgui.TableColumnFlags_.width_fixed, 200)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(source.issues))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    issue = source.issues[index]
                    imgui.table_next_row()
                    for cell in (
                        issue.image_key or "—",
                        str(issue.path),
                        issue.location,
                        issue.message,
                        issue.original or "—",
                    ):
                        imgui.table_next_column()
                        imgui.text_unformatted(cell)
            imgui.end_table()
        imgui.tree_pop()


def box_records(source: AssociatedSource, owner: FileSession) -> None:
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
    )
    if not imgui.begin_table("Prepared boxes", 8, flags, (-1, 170)):
        return
    for name in (
        "Source row",
        "Class / ID",
        "Score",
        "Original",
        "Convention",
        "Pixel xyxy",
        "Location",
        "Diagnostic",
    ):
        imgui.table_setup_column(name, imgui.TableColumnFlags_.width_fixed, 180)
    imgui.table_headers_row()
    clipper = imgui.ListClipper()
    clipper.begin(len(source.boxes))
    while clipper.step():
        for index in range(clipper.display_start, clipper.display_end):
            box = source.boxes[index]
            record = box.box.record
            imgui.push_id(index)
            imgui.table_next_row()
            imgui.table_next_column()
            if imgui.selectable(
                f"{box.origin.row_id}##Box source row",
                owner.images.overlay.selected == box,
            )[0]:
                owner.images.overlay.select(box, owner)
            for cell in (
                f"{record.class_name} / {record.class_id}",
                str(record.score) if record.score is not None else "—",
                str(record.original),
                record.coordinates.value,
                str(box.box.xyxy),
                f"{record.asset.path}: {record.location}",
                "; ".join(box.box.diagnostics),
            ):
                imgui.table_next_column()
                imgui.text_unformatted(cell)
            imgui.pop_id()
    imgui.end_table()
