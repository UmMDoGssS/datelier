"""Version-two whole-session recipes, including recoverable source drafts."""

import math
import string
from dataclasses import dataclass

from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.io.types import (
    ImportFormat,
    ImportOptions,
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

    def validate(self) -> None:
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
        identities = {file.identity for file in self.files}
        if (
            not self.files
            or len(identities) != len(self.files)
            or self.active_id not in identities
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
