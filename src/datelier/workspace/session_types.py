"""Version-two whole-session recipes, including recoverable source drafts."""

import math
import string
from dataclasses import dataclass

from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.inspection.objects.types import NodePath
from datelier.io.types import (
    ImportFormat,
    ImportOptions,
    ObjectOptions,
    validate_import_options,
    validate_source_path,
)
from datelier.workspace.layout import valid_layout
from datelier.workspace.types import Workspace


@dataclass(frozen=True)
class SourceDraft:
    path: str
    format: ImportFormat
    options: ImportOptions

    def validate(self) -> None:
        validate_source_path(self.path)
        validate_import_options(self.format, self.options)


@dataclass(frozen=True)
class SessionFile:
    identity: str
    recipe: Workspace | None = None
    draft: SourceDraft | None = None
    selection: tuple[int, ...] = ()
    panel_scroll: tuple[tuple[str, float, float], ...] = ()
    name: str = ""
    record_views: tuple[SessionFile, ...] = ()
    active_view: str | None = None
    object_path: NodePath = ()
    object_focus: NodePath = ()
    object_expanded: tuple[NodePath, ...] = ()

    def validate(self) -> None:
        ObjectOptions(node_path=self.object_path)
        ObjectOptions(node_path=self.object_focus)
        if len(self.object_expanded) > 1024:
            raise ValueError("Save at most 1024 expanded object nodes")
        for path in self.object_expanded:
            ObjectOptions(node_path=path)
        if len(self.name) > 4096 or len(self.record_views) > 32:
            raise ValueError("Record view names or count exceed saved bounds")
        identities = {view.identity for view in self.record_views}
        if len(identities) != len(self.record_views) or self.identity in identities:
            raise ValueError("Record view identities must be distinct")
        if self.active_view is not None and self.active_view not in identities:
            raise ValueError("Active record view is unavailable")
        for view in self.record_views:
            if view.record_views:
                raise ValueError("Record views cannot contain additional views")
            if (
                self.recipe is None
                or view.recipe is None
                or (
                    self.recipe.source.path != view.recipe.source.path
                    or not isinstance(self.recipe.options, ObjectOptions)
                    or not isinstance(view.recipe.options, ObjectOptions)
                    or view.recipe.options.node_path is None
                )
            ):
                raise ValueError(
                    "Record views must refer to nodes in their owning source"
                )
            view.validate()
        if (
            not self.identity
            or len(self.identity) > 64
            or any(
                c not in (string.ascii_letters + string.digits + "-_")
                for c in self.identity
            )
        ):
            raise ValueError("Invalid saved file identity")
        if self.recipe is not None and self.draft is not None:
            raise ValueError("A tab has one source recipe or draft")
        if self.recipe is not None:
            self.recipe.validate()
        if self.draft is not None:
            self.draft.validate()
        if (
            len(self.selection) > 10_000
            or len(set(self.selection)) != len(self.selection)
            or any(row < 0 for row in self.selection)
        ):
            raise ValueError(
                "Selections require at most 10,000 distinct nonnegative row IDs"
            )
        if self.selection and self.recipe is None:
            raise ValueError("A blank/draft tab cannot have a saved row selection")
        if len(self.panel_scroll) > 32 or len(
            {name for name, _, _ in self.panel_scroll}
        ) != len(self.panel_scroll):
            raise ValueError("Save at most one scroll position per panel")
        if any(
            not name or not math.isfinite(x) or not math.isfinite(y) or min(x, y) < 0
            for name, x, y in self.panel_scroll
        ):
            raise ValueError("Panel scroll positions must be finite and nonnegative")


@dataclass(frozen=True)
class SessionWorkspace:
    files: tuple[SessionFile, ...]
    active_id: str
    comparisons: tuple[ComparisonSettings, ...] = ()
    layout: str = ""
    hidden_windows: tuple[str, ...] = ()
    version: int = 2

    def validate(self) -> None:
        if self.version != 2:
            raise ValueError(f"Unsupported session workspace version: {self.version}")
        all_files = tuple(f for file in self.files for f in (file, *file.record_views))
        identities = {file.identity for file in all_files}
        if (
            not self.files
            or len(identities) != len(all_files)
            or self.active_id not in {file.identity for file in self.files}
        ):
            raise ValueError("Session files must be unique and include the active tab")
        for file in self.files:
            file.validate()
        if len(self.comparisons) > 32:
            raise ValueError("Save at most 32 profile comparisons")
        for comparison in self.comparisons:
            comparison.validate()
            if any(source.file_id not in identities for source in comparison.sources):
                raise ValueError("Comparison mapping refers to a closed file")
        if not valid_layout(self.layout):
            raise ValueError("Unusable session dock layout")
        if len(self.hidden_windows) > 32 or len(set(self.hidden_windows)) != len(
            self.hidden_windows
        ):
            raise ValueError("Invalid hidden panel list")
