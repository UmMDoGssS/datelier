"""Complete worker-prepared JSON values, with virtual lines and horizontal scroll."""

from imgui_bundle import imgui

from datelier.inspection.records.types import RecordField


def show_nested(field: RecordField, *, gallery: bool) -> None:
    imgui.text_unformatted(field.name)
    assert field.lines is not None
    if imgui.begin_child(
        "Nested value",
        (0, 80 if gallery else 0),
        window_flags=imgui.WindowFlags_.horizontal_scrollbar,
    ):
        clipper = imgui.ListClipper()
        clipper.begin(len(field.lines), imgui.get_text_line_height_with_spacing())
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                imgui.text_unformatted(field.lines[index])
    imgui.end_child()
