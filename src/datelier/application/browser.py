"""Prepared directory metadata, independent drafts and safe abandoned listings."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.core import JobExecutor
from datelier.io.catalog import DirectoryListing, list_directory


class EntryKind(StrEnum):
    FOLDER = "Folder"
    FILE = "File"


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    path: Path
    kind: EntryKind
    description: str = ""


class DirectoryController:
    def __init__(self, executor: Executor) -> None:
        self.path = str(Path.cwd())
        self.direct = ""
        self.search = ""
        self.listing: DirectoryListing | None = None
        self.entries: tuple[DirectoryEntry, ...] = ()
        self.shown: tuple[DirectoryEntry, ...] = ()
        self.message = ""
        self.selected: set[Path] = set()
        self.closed = False
        self._executor = JobExecutor(executor, max_workers=1, name="browser")
        self._future: Future[DirectoryListing] | None = None
        self._search = ""
        self._indexed: tuple[tuple[str, DirectoryEntry], ...] = ()

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request(self, path: Path) -> None:
        if self.closed:
            raise ValueError("The file browser is closed")
        self.cancel()
        self.path = str(path.expanduser())
        self.listing = None
        self.entries = self.shown = ()
        self._indexed = ()
        self._future = self._executor.submit(list_directory, path)
        self.message = "Listing supported files…"

    @property
    def detail(self) -> str:
        return "\n".join(self.listing.diagnostics[:4]) if self.listing else ""

    def browse(self) -> None:
        if not self.path.strip():
            raise ValueError("Enter a folder path")
        self.request(Path(self.path))

    def parent(self) -> None:
        self.request(Path(self.path).expanduser().parent)

    def poll(self) -> None:
        if self.closed:
            return
        if self._future and self._future.done():
            future, self._future = self._future, None
            try:
                self.listing = future.result()
                self.path = str(self.listing.directory)
                self.entries = tuple(
                    DirectoryEntry(p.name, p, EntryKind.FOLDER)
                    for p in self.listing.folders
                ) + tuple(
                    DirectoryEntry(f.name, f.path, EntryKind.FILE, f.format.value)
                    for f in self.listing.files
                )
                self._indexed = tuple((e.name.casefold(), e) for e in self.entries)
                self.message = f"{len(self.listing.files)} supported files"
                self._filter()
            except Exception as error:
                self.listing = None
                self.message = (
                    f"Cannot list folder: {error}. Choose another folder or retry."
                )
        if self._search != self.search:
            self._filter()

    def _filter(self) -> None:
        self._search = self.search
        query = self.search.casefold()
        self.shown = tuple(entry for name, entry in self._indexed if query in name)

    def toggle(self, path: Path) -> None:
        if (
            self.closed
            or self.busy
            or not any(
                e.kind == EntryKind.FILE and e.path == path for e in self.entries
            )
        ):
            raise ValueError("That file is no longer available in this listing")
        if path in self.selected:
            self.selected.remove(path)
        else:
            self.selected.add(path)

    def select_all(self) -> None:
        self.selected = {e.path for e in self.shown if e.kind == EntryKind.FILE}

    def selected_paths(self) -> tuple[Path, ...]:
        if self.closed or self.busy or not self.selected:
            raise ValueError("Choose files from the current folder")
        return tuple(sorted(self.selected))

    def collection_paths(self) -> tuple[Path, ...]:
        if self.closed or self.busy or self.listing is None:
            raise ValueError("Choose a folder before opening a media collection")
        return (self.listing.directory,)

    def direct_paths(self) -> tuple[Path, ...]:
        if self.closed or not self.direct.strip():
            raise ValueError("Enter a file or folder path")
        return (Path(self.direct.strip()),)

    def cancel(self) -> None:
        if self._future:
            self._future.cancel()
            self.message = "Listing abandoned; executing work may still finish."
        self._future = None
        self.selected.clear()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.cancel()
        self.listing = None
        self.entries = self.shown = ()
        self._indexed = ()
        self._executor.shutdown(wait=False, cancel_futures=True)
