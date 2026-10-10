"""Strict JSON codec for the finite set of typed workspace recipe records.

Only registered dataclasses are constructed. File contents never select Python
imports or executable classes. Field annotations enforce shapes before replay.
"""

import math
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import TypeAliasType, cast, get_args, get_origin, get_type_hints

from datelier.analysis.parameters import EXTRA_DEFAULTS
from datelier.analysis.types import (
    AnalysisRequest,
    KMeansParameters,
    PCAParameters,
    Preprocessing,
    TSNEParameters,
    UMAPParameters,
)
from datelier.inspection.annotations.overlay import OverlayClass, OverlaySettings
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
)
from datelier.inspection.annotations.types import AnnotationClass
from datelier.inspection.annotations.view_settings import AnnotationViewSettings
from datelier.inspection.arrays.mapping import ArrayRecordMapping, SupportingArray
from datelier.inspection.arrays.slices import SliceSettings
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioScope,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.playback.settings import PlaybackSettings
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_types import SignalViewSettings
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.exploration import PlotSettings
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
)
from datelier.inspection.images.profile_types import ImageProfileSettings, ImageScope
from datelier.inspection.images.settings import ImageProfileViewSettings, ImageSettings
from datelier.inspection.images.types import ImageDisplay
from datelier.inspection.images.viewport import ImageViewport
from datelier.inspection.presentation import TablePresentation
from datelier.inspection.records.types import InspectSettings
from datelier.inspection.references.types import ReferenceMapping, ReferenceSettings
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
)
from datelier.inspection.text.types import (
    TextScope,
    TextSettings,
    TokenizerReference,
    TokenSettings,
    TrainingSettings,
)
from datelier.inspection.text.viewport import TextViewport
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
from datelier.pipeline.operations import Filter, SelectColumns, SetColumnRole, Sort
from datelier.pipeline.types import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
)
from datelier.plotting.categories import CategorySettings
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.recent import RecentSource
from datelier.workspace.session_types import SessionFile, SessionWorkspace, SourceDraft
from datelier.workspace.types import Workspace, WorkspaceSource, WorkspaceViews

RECORDS = (
    AudioCollectionSettings,
    AudioScope,
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
    PlaybackSettings,
    SignalViewSettings,
    AudioRange,
    AudioThresholds,
    AudioSettings,
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
    AnnotationViewSettings,
    OverlayClass,
    OverlaySettings,
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    AnnotationClass,
    ImageProfileSettings,
    ImageScope,
    ImageProfileViewSettings,
    ImageSettings,
    ImageDisplay,
    ImageViewport,
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
    TextViewport,
    TextScope,
    TrainingSettings,
    TextSettings,
    TokenSettings,
    TokenizerReference,
    ArrayRecordMapping,
    SupportingArray,
    SliceSettings,
    ArrayOptions,
    CheckpointOptions,
    InspectSettings,
    TablePresentation,
    ReferenceSettings,
    ReferenceMapping,
    *(type(p) for p in EXTRA_DEFAULTS.values()),
    Workspace,
    SessionFile,
    SessionWorkspace,
    SourceDraft,
    ComparisonSettings,
    ComparisonSource,
    RecentSource,
    WorkspaceSource,
    WorkspaceViews,
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
    AnalysisRequest,
    Preprocessing,
    PCAParameters,
    TSNEParameters,
    UMAPParameters,
    KMeansParameters,
    PlotSettings,
    DistributionSettings,
    CategorySettings,
)


def encode(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float) and not math.isfinite(value):
        return {"float": "nan" if math.isnan(value) else str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return [encode(item) for item in value]
    if type(value) in RECORDS and is_dataclass(value):
        return {
            "kind": type(value).__name__,
            **{f.name: encode(getattr(value, f.name)) for f in fields(value)},
        }
    raise ValueError(f"Unsupported recipe value: {type(value).__name__}")


def decode_record[T](cls: type[T], value: object) -> T:
    if cls not in RECORDS or not is_dataclass(cls) or not isinstance(value, dict):
        raise ValueError("Expected a registered recipe object")
    record = cast(dict[str, object], value)
    if record.get("kind") != cls.__name__:
        raise ValueError(f"Expected {cls.__name__} recipe")
    names = {f.name for f in fields(cls)}
    if set(record) - names - {"kind"}:
        raise ValueError(f"Unknown fields in {cls.__name__}")
    # Reflection is confined to trusted local dataclasses, never file-supplied types.
    annotations = cast(dict[str, object], get_type_hints(cls))
    arguments = {
        name: decode(annotations[name], item)
        for name, item in record.items()
        if name != "kind"
    }
    if cls is ArrayOptions and "record_table" not in arguments:
        # Existing workspaces address member metadata rows, not first-axis records.
        arguments["record_table"] = False
    try:
        return cast(T, cls(**arguments))
    except TypeError as error:
        raise ValueError(f"Invalid {cls.__name__} fields: {error}") from error


def decode(annotation: object, value: object) -> object:
    if isinstance(annotation, TypeAliasType):
        return decode(annotation.__value__, value)
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is types.UnionType:
        for option in args:
            try:
                return decode(option, value)
            except ValueError:
                pass
        raise ValueError("Recipe value does not match a supported field type")
    if origin is tuple:
        if not isinstance(value, list):
            raise ValueError("Expected a recipe list")
        items = cast(list[object], value)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(decode(args[0], item) for item in items)
        if len(items) != len(args):
            raise ValueError("Wrong number of tuple values")
        return tuple(decode(t, item) for t, item in zip(args, items, strict=True))
    if annotation is type(None) and value is None:
        return None
    if annotation in (str, int, bool) and type(value) is annotation:
        return value
    if annotation is float:
        if type(value) in (int, float):
            return float(cast(int | float, value))
        if isinstance(value, dict) and value in (
            {"float": "nan"},
            {"float": "inf"},
            {"float": "-inf"},
        ):
            return float(cast(str, value["float"]))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            return annotation(value)
        except (ValueError, TypeError) as error:
            raise ValueError("Unknown recipe enum value") from error
    if isinstance(annotation, type) and annotation in RECORDS:
        return decode_record(annotation, value)
    raise ValueError("Invalid recipe field type or value")
