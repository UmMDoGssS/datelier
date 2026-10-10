"""Frame-local interaction targets, namespaced independently of display labels."""

from dataclasses import dataclass, field

from datelier.core.dataset import DatasetRevision


@dataclass(frozen=True)
class ViewScope:
    file_id: str
    view_id: str = ""
    revision: DatasetRevision | None = None


@dataclass(frozen=True)
class TargetKey:
    scope: ViewScope
    path: tuple[str, ...]


@dataclass
class GuiProbe:
    targets: dict[TargetKey, tuple[float, float]] = field(default_factory=dict)

    def begin_frame(self) -> None:
        self.targets.clear()

    def record(
        self, scope: ViewScope, path: tuple[str, ...], point: tuple[float, float]
    ) -> None:
        self.targets[TargetKey(scope, path)] = point

    def point(self, scope: ViewScope, *path: str) -> tuple[float, float] | None:
        return self.targets.get(TargetKey(scope, path))
