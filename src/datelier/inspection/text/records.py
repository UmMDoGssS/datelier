"""Worker-side full text reads with distinct null/empty/decoding outcomes."""

import hashlib
from pathlib import Path

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.references.index import ReferenceIndex, resolve
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.types import (
    TextDocument,
    TextOrigin,
    TextSource,
    TextStatus,
)


def read_document(
    dataset: Dataset,
    file_id: str,
    column: str,
    position: int,
    *,
    source: TextSource = TextSource.AUTO,
    encoding: str = "utf8",
    references: ReferenceSettings | None = None,
    index: ReferenceIndex | None = None,
) -> TextDocument:
    table = dataset.table
    if column not in table.columns or not 0 <= position < table.height:
        raise ValueError("Text field or record is unavailable")
    if table.schema[column] != pl.String:
        raise ValueError("Choose a physical String field for text inspection")
    origin = TextOrigin(
        file_id, dataset.revision, int(dataset.row_ids[position]), column
    )
    value = table.get_column(column)[position]
    if value is None:
        return TextDocument(origin, TextStatus.NULL)
    external = source == TextSource.EXTERNAL or (
        source == TextSource.AUTO
        and dataset.role(column).role in (ColumnRole.EXTERNAL_TEXT, ColumnRole.PATH)
    )
    if not external:
        return TextDocument(
            origin, TextStatus.READY if value else TextStatus.EMPTY, value
        )
    path: Path | None = None
    try:
        resolution = resolve(
            dataset.source.path, column, value, references or ReferenceSettings(), index
        )
        asset = resolution.asset
        if asset is None:
            return TextDocument(origin, TextStatus.ERROR, diagnostic=resolution.message)
        path = asset.path
        payload = path.read_bytes()
        text = payload.decode(encoding, errors="strict")
        after = path.stat()
        if (after.st_size, after.st_mtime_ns) != (asset.size, asset.modified_ns):
            raise ValueError("Text source changed during reading; retry")
        return TextDocument(
            origin,
            TextStatus.READY if text else TextStatus.EMPTY,
            text,
            path=str(path),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
    except (OSError, UnicodeError, LookupError, ValueError) as error:
        return TextDocument(
            origin,
            TextStatus.ERROR,
            diagnostic=f"Cannot decode text ({encoding}): {error}",
            path=str(path) if path else None,
        )
