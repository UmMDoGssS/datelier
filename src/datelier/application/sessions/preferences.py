"""Background preference I/O and recent-source state, with no native rendering."""

from concurrent.futures import Executor, Future
from dataclasses import replace
from pathlib import Path

from datelier.core import JobExecutor
from datelier.workspace.preferences import (
    Preferences,
    read_preferences,
    save_preferences,
)
from datelier.workspace.recent import RecentSource, remember


class PreferenceController:
    def __init__(self, path: Path | None, executor: Executor) -> None:
        self.path = path
        self.value = Preferences()
        self.message = ""
        self.ready = path is None
        self.changed = 0
        self._executor = JobExecutor(executor, max_workers=1, name="preferences")
        self._read: Future[tuple[Preferences, str]] | None = (
            self._executor.submit(read_preferences, path) if path else None
        )
        self._write: Future[None] | None = None

    def poll(self) -> None:
        if self._read and self._read.done():
            future, self._read = self._read, None
            try:
                self.value, self.message = future.result()
            except Exception as error:
                self.message = f"Preferences failed: {error}"
            self.ready = True
            self.changed += 1
        if self._write and self._write.done():
            future, self._write = self._write, None
            try:
                future.result()
                self.message = "Preferences saved."
            except Exception as error:
                self.message = f"Preferences failed: {error}"

    def remember(self, source: RecentSource) -> None:
        self.value = replace(self.value, recent=remember(self.value.recent, source))

    def save(self, value: Preferences, sources: tuple[Path, ...]) -> None:
        self.value = value
        if self.path is not None:
            self._write = self._executor.submit(
                save_preferences, self.path, value, sources=sources
            )

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
