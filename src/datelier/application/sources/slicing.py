"""GUI-free editable slice recipes; malformed drafts never start payload work."""

from dataclasses import replace

from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.arrays.windows import plan_window
from datelier.inspection.heatmaps import Colormap


def indices(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(value.strip()) for value in text.split(",") if value.strip())
    except ValueError as error:
        raise ValueError("Use comma-separated integer axes or positions") from error


class SliceDraft:
    def __init__(self) -> None:
        self.axes = self.fixed = self.starts = self.counts = ""
        self.field: str | None = None
        self.component = "Magnitude"
        self.colormap = Colormap.BLUE_YELLOW
        self.manual = False
        self.low, self.high = 0.0, 1.0
        self._bound: SliceSettings | None = None

    @property
    def bound(self) -> SliceSettings | None:
        return self._bound

    def bind(self, settings: SliceSettings) -> None:
        if settings == self._bound:
            return
        if (
            self._bound is not None
            and replace(settings, fixed=self._bound.fixed) == self._bound
        ):
            self._bound = settings
            self.fixed = ",".join(map(str, settings.fixed))
            return
        self._bound = settings
        for name in ("axes", "fixed", "starts", "counts"):
            setattr(self, name, ",".join(map(str, getattr(settings, name))))
        self.field, self.component, self.colormap = (
            settings.field,
            settings.component,
            settings.colormap,
        )
        self.manual = settings.value_range is not None
        self.low, self.high = settings.value_range or (0.0, 1.0)

    def build(self, shape: tuple[int, ...], fields: tuple[str, ...]) -> SliceSettings:
        if self._bound is None:
            raise ValueError("Choose an array or tensor before preparing its values")
        axes = indices(self.axes)
        result = replace(
            self._bound,
            axes=axes,
            fixed=indices(self.fixed),
            starts=indices(self.starts),
            counts=indices(self.counts),
            scalar=not axes,
            field=self.field,
            component=self.component,
            colormap=self.colormap,
            value_range=(self.low, self.high) if self.manual else None,
        )
        plan_window(shape, 1, result)
        if self.field is not None and self.field not in fields:
            raise ValueError("Selected structured field is unavailable")
        return result
