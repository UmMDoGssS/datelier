"""Array controls dispatch jobs; rendering consumes only prepared bounded data."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.arrays.plots import plot_slice
from datelier.gui.heatmaps import HeatmapControls
from datelier.inspection.arrays.slices import PreparedSlice, SliceSettings

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession
    from datelier.inspection.arrays.jobs import ArrayJobs


@dataclass
class ArrayView:
    plot_frames: int = 0
    prepare_pixel: tuple[float, float] = (0, 0)
    raw_columns: dict[str, int] = field(default_factory=dict)
    plotted: dict[str, SliceSettings] = field(default_factory=dict)
    heatmap_controls: dict[str, HeatmapControls] = field(default_factory=dict)

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
        if (
            len(axes) == 2
            and member.dtype is not None
            and member.dtype.kind in "biufcV"
        ):
            self.configure_heatmap(owner.identity, jobs)
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
        self.show_prepared(owner)
        imgui.pop_id()

    def configure_heatmap(self, identity: str, jobs: ArrayJobs) -> None:
        controls = self.heatmap_controls.setdefault(identity, HeatmapControls())
        bounds = jobs.active.finite_range if jobs.active is not None else None
        value_range, colormap = controls.show(
            jobs.settings.value_range, jobs.settings.colormap, bounds
        )
        jobs.settings = replace(
            jobs.settings, value_range=value_range, colormap=colormap
        )

    def show_prepared(self, owner: FileSession) -> None:
        jobs = owner.arrays
        self.render_prepared(owner.identity, jobs.active, jobs.settings)

    def render_prepared(
        self, identity: str, active: PreparedSlice | None, settings: SliceSettings
    ) -> None:
        if active is not None:
            imgui.separator()
            imgui.text_wrapped(
                f"Prepared {active.settings.member}: axes {active.axes}, "
                f"fixed {active.settings.fixed}, "
                f"starts {active.starts}, window {active.raw.shape}"
            )
            if active.settings != settings:
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
                    f"{active.nonfinite:,} nonfinite values; "
                    "magenta heatmap cells and vector gaps. "
                    "Raw values are shown below."
                )
            if active.diagnostic:
                imgui.text_wrapped(active.diagnostic)
            self._plot(active, identity)
            self.show_raw(identity, active)

    def _plot(self, data: PreparedSlice, identity: str) -> None:
        if plot_slice(data, self.plotted.get(identity) != data.settings):
            self.plot_frames += 1
            self.plotted[identity] = data.settings

    def show_raw(self, identity: str, data: PreparedSlice) -> None:
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
