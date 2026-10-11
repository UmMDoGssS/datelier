"""Trusted tabular recipe records; never selected by file-supplied imports."""

from datelier.inspection.arrays import ArrayRecordMapping, SupportingArray
from datelier.inspection.arrays.slices import SliceSettings
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.exploration import PlotSettings
from datelier.inspection.presentation import TablePresentation
from datelier.inspection.records import InspectSettings
from datelier.inspection.references import ReferenceMapping, ReferenceSettings
from datelier.io.types import (
    ArrayOptions,
    CheckpointOptions,
    CsvOptions,
    JsonOptions,
    MediaOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.pipeline import Filter, SelectColumns, SetColumnRole, Sort
from datelier.pipeline.transforms import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
)
from datelier.plotting.categories import CategorySettings
from datelier.plotting.distributions import DistributionSettings

RECORDS = (
    ArrayRecordMapping,
    SupportingArray,
    SliceSettings,
    ArrayOptions,
    CheckpointOptions,
    InspectSettings,
    TablePresentation,
    ReferenceSettings,
    ReferenceMapping,
    ComparisonSettings,
    ComparisonSource,
    CsvOptions,
    MediaOptions,
    JsonOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
    Sort,
    Filter,
    SelectColumns,
    SetColumnRole,
    CastColumn,
    FillMissing,
    DropMissing,
    Lookup,
    DerivedColumn,
    PlotSettings,
    DistributionSettings,
    CategorySettings,
)
