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
    LIST = "List"
    LIST_NUMERIC = "list[numeric]"
    LIST_CATEGORY = "list[category]"
    LIST_TEXT = "list[text]"
    LIST_IDENTIFIER = "list[id]"
    LIST_TEMPORAL = "list[temporal]"
    LIST_OBJECT = "list[object]"
    OBJECT = "Object"
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
    if isinstance(dtype, (pl.List, pl.Array)):
        leaf = list_leaf_dtype(dtype)
        return (
            (
                ColumnRole.LIST_NUMERIC,
                ColumnRole.LIST_CATEGORY,
                ColumnRole.LIST_IDENTIFIER,
                ColumnRole.LIST,
            )
            if leaf.is_numeric()
            else (
                ColumnRole.LIST_CATEGORY,
                ColumnRole.LIST_TEXT,
                ColumnRole.LIST_IDENTIFIER,
                ColumnRole.LIST,
            )
            if leaf == pl.String
            else (ColumnRole.LIST_CATEGORY, ColumnRole.LIST_IDENTIFIER, ColumnRole.LIST)
            if leaf in (pl.Boolean, pl.Categorical) or isinstance(leaf, pl.Enum)
            else (ColumnRole.LIST_TEMPORAL, ColumnRole.LIST)
            if leaf.is_temporal()
            else (ColumnRole.LIST_OBJECT, ColumnRole.LIST)
            if isinstance(leaf, pl.Struct)
            else (ColumnRole.LIST,)
        )
    if isinstance(dtype, pl.Struct):
        return (ColumnRole.OBJECT,)
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
            if not dtype.is_nested()
            and allowed_roles(dtype) != (ColumnRole.UNSUPPORTED,)
            else None
        )
        unique = bool(nonnull and distinct == nonnull)
        # Named IDs are retained outside the first source column.
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", series.name).lower()
        id_name = bool(re.search(r"(^|[^a-z0-9])(id|index)($|[^a-z0-9])", words))
        recognizable = _recognize_strings(series) if dtype == pl.String else None
        old = prior.get(series.name)
        if old is not None and old.dtype == str(dtype):
            # Generic inferred lists from older versions gain an element role;
            # explicit saved List overrides retain their physical-type fallback.
            inferred, reason = (
                _infer_list(series)
                if old.inferred == ColumnRole.LIST
                else (old.inferred, old.reason)
            )
        elif isinstance(dtype, (pl.List, pl.Array)):
            inferred, reason = _infer_list(series)
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
LIST_ROLES = (
    ColumnRole.LIST,
    ColumnRole.LIST_NUMERIC,
    ColumnRole.LIST_CATEGORY,
    ColumnRole.LIST_TEXT,
    ColumnRole.LIST_IDENTIFIER,
    ColumnRole.LIST_TEMPORAL,
    ColumnRole.LIST_OBJECT,
)
_LIST_ELEMENTS = {
    ColumnRole.LIST_NUMERIC: ColumnRole.NUMERIC,
    ColumnRole.LIST_CATEGORY: ColumnRole.CATEGORY,
    ColumnRole.LIST_TEXT: ColumnRole.TEXT,
    ColumnRole.LIST_IDENTIFIER: ColumnRole.IDENTIFIER,
    ColumnRole.LIST_TEMPORAL: ColumnRole.TEMPORAL,
    ColumnRole.LIST_OBJECT: ColumnRole.OBJECT,
}


def list_element_role(role: ColumnRole, dtype: pl.DataType) -> ColumnRole:
    """Resolve explicit list meaning and legacy generic-list physical defaults."""
    if role in _LIST_ELEMENTS:
        return _LIST_ELEMENTS[role]
    if role != ColumnRole.LIST:
        return role
    leaf = list_leaf_dtype(dtype)
    return (
        ColumnRole.NUMERIC
        if leaf.is_numeric()
        else ColumnRole.TEMPORAL
        if leaf.is_temporal()
        else ColumnRole.CATEGORY
        if leaf in (pl.String, pl.Boolean, pl.Categorical) or isinstance(leaf, pl.Enum)
        else ColumnRole.OBJECT
        if isinstance(leaf, pl.Struct)
        else ColumnRole.UNSUPPORTED
    )


def list_leaf_dtype(dtype: pl.DataType) -> pl.DataType:
    while isinstance(dtype, (pl.List, pl.Array)):
        inner = dtype.inner
        dtype = inner if isinstance(inner, pl.DataType) else inner()
    return dtype


def _infer_list(series: pl.Series) -> tuple[ColumnRole, str]:
    dtype = series.dtype
    leaf = list_leaf_dtype(dtype)
    default = allowed_roles(dtype)[0]
    if leaf != pl.String:
        return default, f"List leaf type is {leaf}; nested lengths remain separate."
    # Bound each expansion and the final Python sample. Never flatten an entire
    # text collection merely to infer its interpretation during import.
    sample = series.head(256)
    while isinstance(sample.dtype, (pl.List, pl.Array)):
        if isinstance(sample.dtype, pl.Array):
            sample = sample.arr.to_list()
        sample = (
            sample.list.head(256)
            .explode(empty_as_null=False, keep_nulls=False)
            .head(256)
        )
    texts = sample.drop_nulls().to_list()
    prose = sum(len(str(value).split()) >= 3 for value in texts)
    if texts and prose / len(texts) >= 0.8:
        return ColumnRole.LIST_TEXT, (
            f"{prose}/{len(texts)} sampled string elements contain prose "
            "(at least 3 words); sample limit 256."
        )
    return ColumnRole.LIST_CATEGORY, (
        f"{len(texts)} sampled string elements have insufficient prose evidence; "
        "use categories by default or override to list[text]. Sample limit: 256."
    )


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
