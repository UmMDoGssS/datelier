"""Tensor controls render from metadata and prepared windows only."""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.objects.types import NodePath, node_label

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


@dataclass
class CheckpointView:
    prepare_pixel: tuple[float, float] = (0, 0)
    node_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    combo_pixel: tuple[float, float] = (0, 0)
    observed_path: NodePath | None = None

    def show(self, owner: FileSession) -> None:
        jobs = owner.checkpoints
        catalog = jobs.catalog
        if catalog is None:
            imgui.text("Opening checkpoint metadata…")
            return
        if not catalog.tensors:
            imgui.text_wrapped(
                "This checkpoint contains primitive metadata and no tensors."
            )
            return
        imgui.push_id(owner.identity)
        path, name = owner.record_views.path, node_label(owner.record_views.path)
        if self.observed_path != path and name in catalog.indices:
            if jobs.settings.member != name:
                jobs.settings = SliceSettings(name)
        self.observed_path = path
        name = jobs.settings.member
        if name not in catalog.indices:
            name = catalog.tensors[0].name
            jobs.settings = SliceSettings(name)
        opened = imgui.begin_combo("Tensor node", name[:256].replace("##", "# #"))
        self.combo_pixel = _pixel()
        if opened:
            clipper = imgui.ListClipper()
            clipper.begin(len(catalog.tensors))
            self.node_pixels.clear()
            while clipper.step():
                for item in range(clipper.display_start, clipper.display_end):
                    info = catalog.tensors[item]
                    label = info.name[:256].replace("##", "# #")
                    if imgui.selectable(f"{label}###tensor{item}", name == info.name)[
                        0
                    ]:
                        name = info.name
                        jobs.settings = SliceSettings(name)
                        owner.record_views.path = info.path
                        self.observed_path = info.path
                    self.node_pixels[info.name] = _pixel()
            imgui.end_combo()
        info = catalog.tensor(name)
        imgui.text_wrapped(f"{info.shape} · {info.dtype} · {info.layout}")
        imgui.text_wrapped(
            f"Strides {info.strides} · offset {info.storage_offset} · "
            f"{info.raw_bytes:,} bytes"
        )
        imgui.text_wrapped(
            "CPU values · "
            + (
                "mapped checkpoint storage"
                if catalog.mapped
                else "legacy preparation reads complete checkpoint storage"
            )
        )
        if info.diagnostic:
            imgui.text_wrapped(info.diagnostic)
        settings = jobs.settings
        axes = (
            ()
            if settings.scalar
            else settings.axes
            or tuple(range(max(0, len(info.shape) - 2), len(info.shape)))
        )
        if any(axis >= len(info.shape) for axis in axes):
            axes = tuple(range(max(0, len(info.shape) - 2), len(info.shape)))
            jobs.message = "Saved tensor axes were adjusted to its current shape."
        if info.shape:
            imgui.push_item_width(100)
            mode = 0 if settings.scalar else len(axes)
            changed, mode = imgui.combo(
                "Tensor display",
                mode,
                ["Scalar", "Vector", "Matrix"][: min(2, len(info.shape)) + 1],
            )
            if changed:
                axes = tuple(range(len(info.shape) - mode, len(info.shape)))
            configured: list[int] = []
            for i, axis in enumerate(axes):
                _, axis = imgui.combo(
                    f"Tensor display axis {i + 1}",
                    axis,
                    [str(j) for j in range(len(info.shape))],
                )
                configured.append(axis)
            axes, scalar = tuple(configured), mode == 0
            imgui.pop_item_width()
        else:
            scalar = True
        fixed = list(settings.fixed or (0,) * len(info.shape))
        if len(fixed) != len(info.shape):
            fixed = [0] * len(info.shape)
        starts, counts = (
            list(settings.starts or (0,) * len(axes)),
            list(settings.counts or (128,) * len(axes)),
        )
        if len(starts) != len(axes) or len(counts) != len(axes):
            starts, counts = [0] * len(axes), [128] * len(axes)
        imgui.push_item_width(100)
        for i, size in enumerate(info.shape):
            if i not in axes:
                _, fixed[i] = imgui.input_int(
                    f"Tensor axis {i} fixed (0–{max(0, size - 1)})", fixed[i]
                )
        for i, axis in enumerate(axes):
            _, starts[i] = imgui.input_int(f"Tensor axis {axis} start", starts[i])
            _, counts[i] = imgui.input_int(f"Tensor axis {axis} count", counts[i])
        imgui.pop_item_width()
        component = settings.component
        if info.dtype.startswith("torch.complex"):
            components = ["Magnitude", "Real", "Imaginary"]
            _, ci = imgui.combo(
                "Tensor complex component", components.index(component), components
            )
            component = components[ci]
        jobs.settings = replace(
            settings,
            axes=axes,
            fixed=tuple(fixed),
            starts=tuple(starts),
            counts=tuple(counts),
            component=component,
            scalar=scalar,
        )
        imgui.begin_disabled(bool(info.diagnostic))
        if imgui.button("Prepare tensor values"):
            try:
                jobs.request(jobs.settings)
            except ValueError as error:
                jobs.message = str(error)
        self.prepare_pixel = _pixel()
        imgui.end_disabled()
        if jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon tensor preparation"):
                jobs.abandon()
                jobs.message = "Result abandoned; executing storage reads may finish."
        imgui.text_wrapped(jobs.message)
        if imgui.collapsing_header("Checkpoint retention"):
            changed, limit = imgui.input_int(
                "Retained checkpoint MiB", jobs.store.limit // (1024 * 1024)
            )
            if changed and limit >= 0:
                jobs.set_retention(limit * 1024 * 1024)
            imgui.text_wrapped(
                f"{jobs.store.stored_bytes:,} logical storage bytes retained. "
                "Mapped byte counts describe virtual storage, not resident memory."
            )
        prepared = jobs.active
        if prepared is not None:
            imgui.text_wrapped(f"Original tensor dtype: {prepared.dtype}")
            owner.array_view.render_prepared(
                owner.identity, prepared.view, jobs.settings
            )
            if prepared.storage is not None and imgui.collapsing_header(
                "Original tensor storage bits"
            ):
                imgui.text_wrapped(prepared.storage.diagnostic)
                owner.array_view.show_raw(owner.identity + ":bits", prepared.storage)
        imgui.pop_id()


def _pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
