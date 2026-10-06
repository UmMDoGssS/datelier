"""Column meaning inferred in data workers, with explicit user overrides."""

import re
from dataclasses import dataclass
from enum import StrEnum

import polars as pl


class ColumnRole(StrEnum):
    NUMERIC = "Numeric"
    CATEGORY = "Categorical"
    TEXT = "Text"
    IDENTIFIER = "Identifier"
    PATH = "Local path"
    IMAGE = "Image"
    AUDIO = "Audio"
    EXTERNAL_TEXT = "External text"
    TEMPORAL = "Temporal"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class RoleInfo:
    name: str
    dtype: str
    inferred: ColumnRole
    distinct: int | None
    nonnull: int
    reason: str
    override: ColumnRole | None = None

    @property
    def role(self) -> ColumnRole:
        return self.override or self.inferred


def allowed_roles(dtype: pl.DataType) -> tuple[ColumnRole, ...]:
    if dtype.is_numeric():
        return (ColumnRole.NUMERIC, ColumnRole.CATEGORY, ColumnRole.IDENTIFIER)
    if dtype == pl.String:
        return (
            ColumnRole.CATEGORY,
            ColumnRole.TEXT,
            ColumnRole.IDENTIFIER,
            ColumnRole.PATH,
            ColumnRole.IMAGE,
            ColumnRole.AUDIO,
            ColumnRole.EXTERNAL_TEXT,
        )
    if dtype in (pl.Boolean, pl.Categorical) or isinstance(dtype, pl.Enum):
        return (ColumnRole.CATEGORY, ColumnRole.IDENTIFIER)
    if dtype.is_temporal():
        return (ColumnRole.TEMPORAL,)
    return (ColumnRole.UNSUPPORTED,)


def infer_roles(
    table: pl.DataFrame, previous: tuple[RoleInfo, ...] = ()
) -> tuple[RoleInfo, ...]:
    overrides = {p.name: p.override for p in previous if p.override is not None}
    result: list[RoleInfo] = []
    prior = {p.name: p for p in previous}
    for index, series in enumerate(table):
        dtype = series.dtype
        nonnull = len(series) - series.null_count()
        distinct = (
            series.n_unique() - int(series.null_count() > 0)
            if allowed_roles(dtype) != (ColumnRole.UNSUPPORTED,)
            else None
        )
        unique = bool(nonnull and distinct == nonnull)
        # Named IDs are retained outside the first source column.
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", series.name).lower()
        id_name = bool(re.search(r"(^|[^a-z0-9])(id|index)($|[^a-z0-9])", words))
        recognizable = _recognize_strings(series) if dtype == pl.String else None
        old = prior.get(series.name)
        if old is not None and old.dtype == str(dtype):
            inferred, reason = old.inferred, old.reason
        elif recognizable is not None:
            inferred, reason = recognizable
        elif (
            index == 0
            and not previous
            and unique
            and nonnull == len(series)
            and (dtype.is_integer() or dtype == pl.String)
        ):
            inferred = ColumnRole.IDENTIFIER
            reason = "First source column: all values are unique and non-null."
        elif unique and id_name and (dtype.is_integer() or dtype == pl.String):
            inferred = ColumnRole.IDENTIFIER
            reason = "Unique non-null values with an ID/index name."
        elif dtype == pl.String and unique:
            inferred = ColumnRole.TEXT
            reason = "Every non-null string is unique."
        elif dtype == pl.String:
            inferred = ColumnRole.CATEGORY
            reason = "Repeated string values form categories."
        else:
            inferred = allowed_roles(dtype)[0]
            reason = f"Inferred from {dtype}."
        override = overrides.get(series.name)
        if override not in allowed_roles(dtype):
            override = None
        result.append(
            RoleInfo(
                series.name, str(dtype), inferred, distinct, nonnull, reason, override
            )
        )
    return tuple(result)


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")
AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus")
TEXT_EXTENSIONS = (".txt", ".md", ".rst", ".log")
REFERENCE_ROLES = (
    ColumnRole.PATH,
    ColumnRole.IMAGE,
    ColumnRole.AUDIO,
    ColumnRole.EXTERNAL_TEXT,
)
PLOTTABLE_ROLES = (ColumnRole.NUMERIC, ColumnRole.CATEGORY, ColumnRole.TEMPORAL)


def _recognize_strings(series: pl.Series) -> tuple[ColumnRole, str] | None:
    """Lexical inference only: no filesystem access and no payload decoding."""
    values = series.rename("value").drop_nulls().head(256).to_list()
    if not values:
        return None
    for role, extensions in (
        (ColumnRole.IMAGE, IMAGE_EXTENSIONS),
        (ColumnRole.AUDIO, AUDIO_EXTENSIONS),
        (ColumnRole.EXTERNAL_TEXT, TEXT_EXTENSIONS),
    ):
        matches = sum(
            str(v).lower().endswith(extensions) and "://" not in str(v) for v in values
        )
        if matches / len(values) >= 0.8:
            return role, (
                f"{matches}/{len(values)} sampled non-null values have {role} "
                "extensions; existence is checked separately. Sample limit: 256."
            )
    paths = sum(
        "://" not in str(v)
        and (
            bool(re.match(r"^(\.?\.?/|~/|/)", str(v)))
            or "/" in str(v)
            and not any(c.isspace() for c in str(v))
        )
        for v in values
    )
    if paths / len(values) >= 0.8:
        return (
            ColumnRole.PATH,
            "At least 80% of up to 256 values use local path syntax.",
        )
    prose = sum(len(str(v).split()) >= 3 for v in values)
    if prose / len(values) >= 0.8:
        return ColumnRole.TEXT, "At least 80% of up to 256 values contain prose."
    return None
