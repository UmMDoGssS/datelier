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
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.exploration import PlotSettings
from datelier.inspection.presentation import TablePresentation
from datelier.inspection.records.types import InspectSettings
from datelier.inspection.references.types import ReferenceMapping, ReferenceSettings
from datelier.io.types import (
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
