"""Directory browsing metadata and cancellation outside frame callbacks."""

from concurrent.futures import Executor, Future
from pathlib import Path

from datelier.core.jobs import JobExecutor
from datelier.io.catalog import DirectoryListing, list_directory


class DirectoryController:
    def __init__(self, executor: Executor) -> None:
        self.path = str(Path.cwd())
        self.listing: DirectoryListing | None = None
        self.message = ""
        self.selected: set[Path] = set()
        self.folder_mode = False
        self._executor = JobExecutor(executor, max_workers=1, name="browser")
        self._future: Future[DirectoryListing] | None = None

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request(self, path: Path) -> None:
        self.cancel()
        self._future = self._executor.submit(list_directory, path)
        self.message = "Listing supported files…"

    def poll(self) -> None:
        if self._future and self._future.done():
            future, self._future = self._future, None
            try:
                self.listing = future.result()
                self.path = str(self.listing.directory)
                self.message = f"{len(self.listing.files)} supported files"
            except Exception as error:
                self.listing = None
                self.message = (
                    f"Cannot list folder: {error}. Choose another folder or retry."
                )

    def cancel(self) -> None:
        if self._future:
            self._future.cancel()
        self._future = None
        self.selected.clear()

    def close(self) -> None:
        self.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)
