"""Typed, GUI-independent import settings, results, and diagnostics."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.core import Dataset
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.checkpoints import CheckpointCatalog
from datelier.inspection.objects import NodePath, ObjectNode


class ImportFormat(StrEnum):
    CSV = "CSV"
    TSV = "TSV"
    JSON = "JSON"
    JSONL = "JSONL"
    PARQUET = "Parquet"
    XML = "XML"
    MEDIA = "Media / text"
    OBJECT = "JSON / TOML object"
    ARRAY = "NumPy array"
    CHECKPOINT = "PyTorch checkpoint"


@dataclass(frozen=True)
class CsvOptions:
    separator: str = ","
    has_header: bool = True
    quote_char: str | None = '"'
    null_values: tuple[str, ...] = ()
    infer_schema_length: int | None = 100
    infer_types: bool = True
    try_parse_dates: bool = False
    skip_rows: int = 0

    def __post_init__(self) -> None:
        for name, value in (("Separator", self.separator), ("Quote", self.quote_char)):
            if value is not None and (
                len(value.encode("utf8")) != 1 or value in "\r\n\x00"
            ):
                raise ValueError(f"{name} must be a single non-newline UTF-8 byte")
        if self.infer_schema_length is not None and self.infer_schema_length < 1:
            raise ValueError("Schema inference rows must be positive or all rows")
        if self.skip_rows < 0:
            raise ValueError("Skipped rows must be nonnegative")


@dataclass(frozen=True)
class JsonOptions:
    read_as_text: bool = False


@dataclass(frozen=True)
class ObjectOptions:
    syntax: str = ""
    node_path: NodePath | None = None
    read_as_text: bool = False

    def __post_init__(self) -> None:
        if self.syntax not in ("", "json", "toml"):
            raise ValueError("Object syntax must be JSON, TOML or automatic")
        if self.node_path is not None and (
            len(self.node_path) > 256
            or any(
                type(k) not in (str, int) or type(k) is int and k < 0
                for k in self.node_path
            )
        ):
            raise ValueError("Node paths require string fields or nonnegative indices")


@dataclass(frozen=True)
class ArrayOptions:
    archive: bool | None = None
    max_header_bytes: int = 10_000
    mapping: ArrayRecordMapping | None = None
    record_table: bool = True

    def mapping_for(
        self, catalog: ArrayCatalog | None, column: str | None
    ) -> ArrayRecordMapping | None:
        if self.mapping is not None:
            return self.mapping
        if not self.record_table or catalog is None or column is None:
            return None
        from datelier.io.arrays.aligned import column_mapping

        return column_mapping(catalog, column)

    def __post_init__(self) -> None:
        if self.mapping is not None:
            self.mapping.validate()
        if not 1 <= self.max_header_bytes <= 16 * 1024 * 1024:
            raise ValueError("Array header limit must be between one byte and 16 MiB")


@dataclass(frozen=True)
class CheckpointOptions:
    max_nodes: int = 200_000
    max_depth: int = 128

    def __post_init__(self) -> None:
        if not 1 <= self.max_nodes <= 1_000_000 or not 1 <= self.max_depth <= 256:
            raise ValueError("Checkpoint metadata node/depth limits are out of range")


@dataclass(frozen=True)
class ParquetOptions:
    columns: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.columns is not None and (
            not self.columns
            or len(set(self.columns)) != len(self.columns)
            or any(not name for name in self.columns)
        ):
            raise ValueError("Selected Parquet columns must be nonempty and unique")


@dataclass(frozen=True)
class XmlOptions:
    record_path: str = "./*"
    namespaces: tuple[tuple[str, str], ...] = ()
    include_attributes: bool = True
    strip_text: bool = True
    null_values: tuple[str, ...] = ()
    infer_types: bool = True
    try_parse_dates: bool = False

    def __post_init__(self) -> None:
        if not self.record_path.strip():
            raise ValueError("XML record path must be nonempty")
        prefixes = [prefix for prefix, _ in self.namespaces]
        if len(set(prefixes)) != len(prefixes) or any(
            not prefix or not uri for prefix, uri in self.namespaces
        ):
            raise ValueError("XML namespaces require unique nonempty prefixes and URIs")


@dataclass(frozen=True)
class MediaOptions:
    text_lines: bool = False
    recursive: bool = True
    manifest: tuple[str, ...] | None = None
    line_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if self.manifest is not None and (
            len(set(self.manifest)) != len(self.manifest)
            or any(
                not m or Path(m).is_absolute() or ".." in Path(m).parts
                for m in self.manifest
            )
        ):
            raise ValueError("Media manifests require distinct relative member paths")
        if len({m for m, _ in self.line_counts}) != len(self.line_counts) or any(
            count < 0 for _, count in self.line_counts
        ):
            raise ValueError("Saved text line counts must be unique and nonnegative")


type ImportOptions = (
    CsvOptions
    | JsonOptions
    | ParquetOptions
    | XmlOptions
    | MediaOptions
    | ObjectOptions
    | ArrayOptions
    | CheckpointOptions
)


def validate_import_options(format: ImportFormat, options: ImportOptions) -> None:
    expected = {
        ImportFormat.CSV: CsvOptions,
        ImportFormat.TSV: CsvOptions,
        ImportFormat.JSON: JsonOptions,
        ImportFormat.JSONL: JsonOptions,
        ImportFormat.PARQUET: ParquetOptions,
        ImportFormat.XML: XmlOptions,
        ImportFormat.MEDIA: MediaOptions,
        ImportFormat.OBJECT: ObjectOptions,
        ImportFormat.ARRAY: ArrayOptions,
        ImportFormat.CHECKPOINT: CheckpointOptions,
    }[format]
    if type(options) is not expected:
        raise ValueError("Import options do not match the saved format")


def validate_source_path(path: str) -> None:
    path.encode("utf8")
    if not path.strip() or "\x00" in path or len(path) > 4096:
        raise ValueError("Invalid source reference path")


class ImportFailure(Exception):
    """An actionable failure that callers can display without a traceback."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"{path.name}: {message}")


@dataclass(frozen=True)
class ImportResult:
    dataset: Dataset
    options: ImportOptions
    diagnostics: tuple[str, ...]
    format: ImportFormat = ImportFormat.CSV
    object_root: ObjectNode | None = None
    array_catalog: ArrayCatalog | None = None
    checkpoint_catalog: CheckpointCatalog | None = None
