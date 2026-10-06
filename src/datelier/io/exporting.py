"""Explicit, atomic CSV/Parquet export of a captured dataset revision."""

import os
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.io.protection import destination_is_source


class ExportFormat(StrEnum):
    CSV = "CSV"
    PARQUET = "Parquet"


class ExportFailure(ValueError):
    pass


@dataclass(frozen=True)
class ExportResult:
    path: Path
    revision: DatasetRevision
    rows: int
    columns: int
    format: ExportFormat


def guard_destination(dataset: Dataset, path: Path, overwrite: bool) -> None:
    source = dataset.source.path.resolve()
    if destination_is_source(path, source):
        raise ExportFailure(
            "Choose a different destination; source files are preserved"
        )
    if path.exists() and not overwrite:
        raise ExportFailure(
            "Destination exists; choose another path or enable replacement"
        )


def export_dataset(
    dataset: Dataset, path: Path, format: ExportFormat, *, overwrite: bool = False
) -> ExportResult:
    path = path.expanduser().resolve()
    temporary: Path | None = None
    try:
        guard_destination(dataset, path, overwrite)
        table = dataset.table
        with NamedTemporaryFile(
            prefix=".datelier-export-", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
        if format == ExportFormat.CSV:
            table.write_csv(temporary)
        elif format == ExportFormat.PARQUET:
            table.write_parquet(temporary)
        else:
            raise ExportFailure("Choose CSV or Parquet")
        guard_destination(dataset, path, overwrite)
        if overwrite:
            os.replace(temporary, path)
        else:
            # Atomic creation also rejects destinations created during preparation.
            os.link(temporary, path)
            temporary.unlink()
        temporary = None
        return ExportResult(path, dataset.revision, table.height, table.width, format)
    except ExportFailure:
        raise
    except Exception as error:
        raise ExportFailure(f"Could not export {path.name}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class DatasetExporter:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self.message = "Choose a destination to export the active table."
        self.result: ExportResult | None = None
        self._executor = JobExecutor(executor, max_workers=1, name="export")
        self._future: Future[ExportResult] | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request(
        self,
        dataset: Dataset,
        path: Path,
        format: ExportFormat,
        *,
        overwrite: bool = False,
    ) -> None:
        if self._closed or self.busy:
            raise ValueError("Export requires an idle exporter")
        self.result = None
        self._future = self._executor.submit(
            export_dataset, dataset, path, format, overwrite=overwrite
        )
        self.message = "Exporting the table selected when export started…"

    def poll(self) -> None:
        if self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.result = future.result()
            self.message = f"Exported {self.result.rows:,} rows to {self.result.path}"
        except Exception as error:
            self.message = f"Export failed: {error}"

    def close(self) -> None:
        self._closed = True
        # An explicitly requested write finishes even if the window closes.
        self._executor.shutdown(wait=False, cancel_futures=False)
