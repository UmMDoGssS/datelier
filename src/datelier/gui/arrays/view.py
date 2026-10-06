"""Array controls dispatch jobs; rendering consumes only prepared bounded data."""

import math
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui, implot

from datelier.inspection.arrays.slices import PreparedSlice, SliceSettings

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


@dataclass
class ArrayView:
    plot_frames: int = 0
    prepare_pixel: tuple[float, float] = (0, 0)
    raw_columns: dict[str, int] = field(default_factory=dict)
    plotted: dict[str, SliceSettings] = field(default_factory=dict)

    def show(self, owner: FileSession) -> None:
        jobs = owner.arrays
        catalog = jobs.catalog
        if catalog is None:
            imgui.text("Opening array metadata…")
            return
        if not catalog.members:
            imgui.text("This archive contains no NPY members.")
            return
        imgui.push_id(owner.identity)
        chosen = jobs.settings.member
        index = catalog.indices.get(chosen, 0)
        changed = False
        label = catalog.members[index].name[:256].replace("##", "# #")
        if imgui.begin_combo("Member", label):
            clipper = imgui.ListClipper()
            clipper.begin(len(catalog.members))
            while clipper.step():
                for item in range(clipper.display_start, clipper.display_end):
                    name = catalog.members[item].name[:256].replace("##", "# #")
                    if imgui.selectable(f"{name}###member{item}", item == index)[0]:
                        changed, index = True, item
            imgui.end_combo()
        member = catalog.members[index]
        if changed or chosen != member.name:
            jobs.settings = SliceSettings(member.name)
        imgui.text_wrapped(
            f"{member.shape} · {member.dtype} · "
            f"{'Fortran' if member.fortran_order else 'C'} order"
        )
        imgui.text_wrapped(
            f"Raw {member.raw_bytes:,} bytes · stored {member.stored_bytes:,} bytes"
        )
        if member.diagnostic:
            imgui.text_wrapped(member.diagnostic)
        settings = jobs.settings
        axes = settings.axes or tuple(
            range(max(0, len(member.shape) - 2), len(member.shape))
        )
        if member.shape:
            mode = min(2, len(axes)) - 1
            changed, mode = imgui.combo("Display", mode, ["Vector", "Matrix"])
            if changed:
                axes = tuple(
                    range(max(0, len(member.shape) - mode - 1), len(member.shape))
                )
            configured: list[int] = []
            for i, axis in enumerate(axes):
                _, axis = imgui.combo(
                    f"Display axis {i + 1}",
                    axis,
                    [str(j) for j in range(len(member.shape))],
                )
                configured.append(axis)
            axes = tuple(configured)
        fixed = list(settings.fixed or (0,) * len(member.shape))
        starts = list(settings.starts or (0,) * len(axes))
        counts = list(settings.counts or (128,) * len(axes))
        if len(fixed) != len(member.shape):
            fixed = [0] * len(member.shape)
        if len(starts) != len(axes):
            starts, counts = [0] * len(axes), [128] * len(axes)
        imgui.push_item_width(100)
        for i, size in enumerate(member.shape):
            if i not in axes:
                _, fixed[i] = imgui.input_int(
                    f"Axis {i} position (0–{max(0, size - 1)})", fixed[i]
                )
        for i, axis in enumerate(axes):
            _, starts[i] = imgui.input_int(f"Axis {axis} window start", starts[i])
            _, counts[i] = imgui.input_int(f"Axis {axis} count", counts[i])
        imgui.pop_item_width()
        dtype_fields = member.dtype.names if member.dtype is not None else None
        selected_field = settings.field
        if dtype_fields:
            fields = ["Raw records", *dtype_fields]
            field_index = (
                fields.index(selected_field) if selected_field in fields else 0
            )
            _, field_index = imgui.combo("Numeric field", field_index, fields)
            selected_field = fields[field_index] if field_index else None
        component = settings.component
        if member.dtype is not None and member.dtype.kind == "c":
            components = ["Magnitude", "Real", "Imaginary"]
            _, component_index = imgui.combo(
                "Complex display", components.index(component), components
            )
            component = components[component_index]
        jobs.settings = replace(
            settings,
            axes=axes,
            fixed=tuple(fixed),
            starts=tuple(starts),
            counts=tuple(counts),
            field=selected_field,
            component=component,
        )
        imgui.begin_disabled(not member.usable)
        if imgui.button("Prepare slice"):
            try:
                jobs.request(jobs.settings)
            except ValueError as error:
                jobs.message = str(error)
        self.prepare_pixel = _pixel()
        imgui.end_disabled()
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon preparation"):
                jobs.abandon()
                jobs.message = "Result abandoned; executing work stops between chunks."
            progress = jobs.store.progress
            if progress is not None:
                name, complete, total = progress
                imgui.text_wrapped(f"Preparing {name}: {complete:,} / {total:,} bytes")
        imgui.text_wrapped(jobs.message)
        if imgui.collapsing_header("Array disk retention"):
            limit = jobs.store.limit // (1024 * 1024)
            changed, limit = imgui.input_int("Retained MiB", limit)
            if changed and limit >= 0:
                jobs.set_retention(limit * 1024 * 1024)
            imgui.text_wrapped(
                f"{jobs.store.stored_bytes:,} temporary bytes. "
                "Oversized selected members are discarded after use."
            )
        active = jobs.active
        if active is not None:
            imgui.separator()
            imgui.text_wrapped(
                f"Prepared {active.settings.member}: axes {active.axes}, "
                f"starts {active.starts}, window {active.raw.shape}"
            )
            if active.settings != jobs.settings:
                imgui.text_wrapped(
                    "Showing the previous prepared slice. "
                    "Prepare to apply the current controls."
                )
            if active.limited:
                imgui.text_wrapped(
                    "Exact window; remaining positions are available "
                    "by changing its start/count."
                )
            if active.nonfinite:
                imgui.text_wrapped(
                    f"{active.nonfinite:,} nonfinite values; gray cells/gaps. "
                    "Raw values are shown below."
                )
            if active.diagnostic:
                imgui.text_wrapped(active.diagnostic)
            self._plot(active, owner.identity)
            self._raw(owner.identity, active)
        imgui.pop_id()

    def _plot(self, data: PreparedSlice, identity: str) -> None:
        if data.numeric is None or data.numeric.size == 0 or not data.axes:
            return
        imgui.text_wrapped(
            f"Finite range: {data.finite_range}. Plot conversion uses float64."
        )
        if len(data.axes) == 1:
            if self.plotted.get(identity) != data.settings:
                implot.set_next_axes_to_fit()
            if implot.begin_plot("Vector values", (-1, 230)):
                implot.setup_axes(f"Axis {data.axes[0]} index", "Value")
                implot.plot_line("Values", data.numeric, xstart=float(data.starts[0]))
                self.plot_frames += 1
                implot.end_plot()
                self.plotted[identity] = data.settings
        elif data.heatmap is not None:
            rows, columns = data.raw.shape
            if not rows or not columns:
                return
            if implot.begin_plot("Matrix heatmap", (-1, 230), implot.Flags_.no_legend):
                row, column = data.starts
                implot.setup_axes(
                    f"Axis {data.axes[1]} index", f"Axis {data.axes[0]} index"
                )
                implot.setup_axes_limits(
                    column,
                    column + columns,
                    row,
                    row + rows,
                    imgui.Cond_.always
                    if self.plotted.get(identity) != data.settings
                    else imgui.Cond_.once,
                )
                implot.push_colormap(implot.Colormap_.viridis)
                implot.plot_heatmap(
                    "Normalized colors",
                    data.heatmap,
                    0,
                    1,
                    "",
                    implot.Point(column, row),
                    implot.Point(column + columns, row + rows),
                )
                implot.pop_colormap()
                implot.push_plot_clip_rect()
                for y, start, count in data.nonfinite_spans:
                    a = implot.plot_to_pixels(float(column + start), float(row + y))
                    b = implot.plot_to_pixels(
                        float(column + start + count), float(row + y + 1)
                    )
                    implot.get_plot_draw_list().add_rect_filled(
                        imgui.ImVec2(min(a.x, b.x), min(a.y, b.y)),
                        imgui.ImVec2(max(a.x, b.x), max(a.y, b.y)),
                        0xFF777777,
                    )
                implot.pop_plot_clip_rect()
                if implot.is_plot_hovered():
                    mouse = implot.get_plot_mouse_pos()
                    y, x = math.floor(mouse.y) - row, math.floor(mouse.x) - column
                    if 0 <= y < rows and 0 <= x < columns:
                        indices = list(
                            data.settings.fixed or (0,) * len(data.source_shape)
                        )
                        indices[data.axes[0]] = row + y
                        indices[data.axes[1]] = column + x
                        imgui.set_tooltip(
                            f"Source index {tuple(indices)}: {data.cells[y][x]}"
                        )
                self.plot_frames += 1
                implot.end_plot()
                self.plotted[identity] = data.settings

    def _raw(self, identity: str, data: PreparedSlice) -> None:
        imgui.text_wrapped("Raw values (cells truncate at 256 characters).")
        if not data.cells:
            imgui.text("Empty slice")
            return
        width = len(data.cells[0])
        start = min(self.raw_columns.get(identity, 0), max(0, width - 1))
        if width > 12:
            if imgui.small_button("Previous raw columns"):
                self.raw_columns[identity] = max(0, start - 12)
            imgui.same_line()
            if imgui.small_button("Next raw columns"):
                self.raw_columns[identity] = min(max(0, width - 12), start + 12)
        columns = min(12, width - start)
        flags = (
            imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
        )
        if imgui.begin_table("Exact raw values", columns + 1, flags, (-1, 170)):
            imgui.table_setup_column("Index")
            for column in range(start, start + columns):
                imgui.table_setup_column(
                    str(column + (data.starts[1] if len(data.starts) > 1 else 0))
                )
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(data.cells))
            while clipper.step():
                for row in range(clipper.display_start, clipper.display_end):
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(str(row + (data.starts[0] if data.starts else 0)))
                    for value in data.cells[row][start : start + columns]:
                        imgui.table_next_column()
                        imgui.text_unformatted(value)
            imgui.end_table()


def _pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
