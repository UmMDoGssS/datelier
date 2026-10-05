"""Version-one referenced workspace recipes; no data or fitted ML artifacts."""

import math
from dataclasses import dataclass, replace

from datelier.analysis_types import Algorithm, AnalysisRequest
from datelier.exploration import PlotSettings
from datelier.import_types import (
    CsvOptions,
    ImportFormat,
    ImportOptions,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.operations import Operation


@dataclass(frozen=True)
class WorkspaceSource:
    path: str
    size_bytes: int
    modified_ns: int
    sha256: str


@dataclass(frozen=True)
class WorkspaceViews:
    tab: str = "Profiles"
    comparison_mode: int = 0
    relationship_mode: int = 0
    profile_index: int = 0
    scatter_index: int = 0
    column_start: int = 0
    target_row: int = 1
    profile_mode: int = 0
    coordinate_source: Algorithm | None = None
    profile_height: float = 0
    comparison_height: float = 0
    scatter_height: float = 0
    relationship_height: float = 0
    color_source: str | None = None
    category_height: float = 0
    profile_selection: tuple[str, ...] | None = None

    def validate(self) -> None:
        if self.profile_selection is not None and len(
            set(self.profile_selection)
        ) != len(self.profile_selection):
            raise ValueError("Profile selection must contain distinct column names")
        if self.tab not in ("Profiles", "Scatter", "Relationships", "Correlations"):
            raise ValueError("Unknown exploration view")
        if not 0 <= self.comparison_mode <= 5 or self.relationship_mode not in (0, 1):
            raise ValueError("Unknown comparison or relationship view")
        if min(self.profile_index, self.scatter_index, self.column_start) < 0:
            raise ValueError("View offsets must be nonnegative")
        if self.target_row < 1:
            raise ValueError("Target row must be positive")
        if not 0 <= self.profile_mode < 5:
            raise ValueError("Unknown profile chart type")
        if self.coordinate_source is not None and self.coordinate_source.is_clustering:
            raise ValueError("Clustering does not supply scatter coordinates")
        if self.color_source not in (
            None,
            "Uniform",
            "Column",
            *(a.value for a in Algorithm if a.is_clustering),
        ):
            raise ValueError("Unknown color source")
        if any(
            not math.isfinite(h) or h != 0 and h < 170
            for h in (
                self.profile_height,
                self.comparison_height,
                self.scatter_height,
                self.relationship_height,
                self.category_height,
            )
        ):
            raise ValueError(
                "Plot heights must be finite and at least 170, or 0 for auto"
            )


@dataclass(frozen=True)
class Workspace:
    source: WorkspaceSource
    format: ImportFormat
    options: ImportOptions
    history: tuple[Operation, ...] = ()
    cursor: int = 0
    analysis: tuple[AnalysisRequest, ...] = ()
    plots: PlotSettings = PlotSettings()
    views: WorkspaceViews = WorkspaceViews()
    version: int = 1

    def validate(self) -> None:
        if self.version != 1:
            raise ValueError(f"Unsupported workspace version: {self.version}")
        source = self.source
        if (
            not source.path
            or source.size_bytes < 0
            or source.modified_ns < 0
            or len(source.sha256) != 64
            or any(c not in "0123456789abcdef" for c in source.sha256)
        ):
            raise ValueError("Invalid workspace source reference")
        expected = {
            ImportFormat.CSV: CsvOptions,
            ImportFormat.TSV: CsvOptions,
            ImportFormat.JSON: JsonOptions,
            ImportFormat.JSONL: JsonOptions,
            ImportFormat.PARQUET: ParquetOptions,
            ImportFormat.XML: XmlOptions,
        }[self.format]
        if not isinstance(self.options, expected):
            raise ValueError("Import options do not match the saved format")
        if len(self.history) > 1_000 or not 0 <= self.cursor <= len(self.history):
            raise ValueError("Workspace history or cursor exceeds supported bounds")
        if len(self.analysis) > len(Algorithm) or len(
            {r.algorithm for r in self.analysis}
        ) != len(self.analysis):
            raise ValueError("Save at most one setting recipe per analysis algorithm")
        for request in self.analysis:
            # Empty features are valid saved controls, but cannot launch analysis.
            replace(request, features=request.features or ("unselected",)).validate()
        if self.analysis:
            first = self.analysis[0]
            if any(
                (r.features, r.preprocessing, r.seed, r.dimensions)
                != (first.features, first.preprocessing, first.seed, first.dimensions)
                for r in self.analysis
            ):
                raise ValueError(
                    "Analysis recipes must share the workbench input settings"
                )
        if self.plots.clusters is not None:
            raise ValueError("Workspaces save ML settings, not fitted results")
        self.plots.validate()
        if len(self.plots.relationship_features) > 16 or len(
            set(self.plots.relationship_features)
        ) != len(self.plots.relationship_features):
            raise ValueError("Choose at most 16 distinct relationship features")
        self.views.validate()
