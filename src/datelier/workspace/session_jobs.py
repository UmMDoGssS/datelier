"""Revision-aware shared-worker session writes, restore and per-file recovery."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass, replace
from pathlib import Path

from datelier.core.dataset import DatasetRevision, SourceReference
from datelier.core.jobs import JobExecutor
from datelier.workspace.session_restore import (
    RestoredSession,
    RestoredSessionFile,
    SourceRecovery,
    restore_session_file,
    restore_session_workspace,
)
from datelier.workspace.session_storage import save_session_workspace
from datelier.workspace.session_types import SessionWorkspace
from datelier.workspace.storage import protect_sources, reference_source

type FileStamp = tuple[DatasetRevision | None, int, bool]
type SessionStamp = tuple[tuple[str, FileStamp], ...]


@dataclass(frozen=True)
class SessionSnapshot:
    workspace: SessionWorkspace
    sources: tuple[tuple[str, SourceReference], ...] = ()


@dataclass(frozen=True)
class SavedSession:
    path: Path
    workspace: SessionWorkspace


def save_snapshot(
    path: Path, snapshot: SessionSnapshot, overwrite: bool
) -> SavedSession:
    path = path.expanduser().resolve()
    protect_sources(path, tuple(source.path for _, source in snapshot.sources))
    if path.exists() and not overwrite:
        raise ValueError("Workspace exists; enable Replace existing workspace")
    ready = {
        file.identity for file in snapshot.workspace.files if file.recipe is not None
    }
    identities = [identity for identity, _ in snapshot.sources]
    if len(set(identities)) != len(identities) or not set(identities) <= ready:
        raise ValueError("Snapshot sources must identify distinct file recipes")
    references = {
        identity: reference_source(source) for identity, source in snapshot.sources
    }
    workspace = replace(
        snapshot.workspace,
        files=tuple(
            replace(file, recipe=replace(file.recipe, source=references[file.identity]))
            if file.recipe is not None and file.identity in references
            else file
            for file in snapshot.workspace.files
        ),
    )
    save_session_workspace(path, workspace)
    return SavedSession(path, workspace)


class SessionJobs:
    def __init__(self, executor: Executor) -> None:
        self._executor = JobExecutor(executor, max_workers=2, name="session-workspace")
        self._future: Future[SavedSession | RestoredSession] | None = None
        self._stamp: SessionStamp = ()
        self._context = 0
        self._recoveries: dict[str, tuple[FileStamp, Future[RestoredSessionFile]]] = {}
        self.message = "Save and reopen all editor tabs in a workspace."
        self.saved: SavedSession | None = None
        self.opened: Path | None = None
        self.completed = 0

    @property
    def busy(self) -> bool:
        return self._future is not None or bool(self._recoveries)

    def request_save(
        self, path: Path, snapshot: SessionSnapshot, *, overwrite: bool = False
    ) -> None:
        if self.busy:
            raise ValueError("Wait for the current workspace job or abandon it")
        self.saved = None
        self._future = self._executor.submit(save_snapshot, path, snapshot, overwrite)
        self.message = "Saving whole-session workspace…"

    def request_restore(
        self, path: Path, stamp: SessionStamp, *, context: int = 0
    ) -> None:
        self.abandon()
        self.saved = None
        self._stamp = stamp
        self._context = context
        self._future = self._executor.submit(restore_session_workspace, path)
        self.message = "Checking sources and restoring editor tabs…"

    def request_recovery(
        self,
        file: RestoredSessionFile,
        revision: FileStamp,
        recovery: SourceRecovery,
    ) -> None:
        previous = self._recoveries.pop(file.file.identity, None)
        if previous is not None:
            previous[1].cancel()
        self._recoveries[file.file.identity] = (
            revision,
            self._executor.submit(restore_session_file, file.file, recovery),
        )
        self.message = "Checking replacement source and replaying its recipe…"

    def poll(
        self, stamp: SessionStamp, *, context: int = 0
    ) -> tuple[RestoredSession | None, tuple[RestoredSessionFile, ...]]:
        restored: RestoredSession | None = None
        if self._future is not None and self._future.done():
            future, self._future = self._future, None
            try:
                result = future.result()
                if isinstance(result, SavedSession):
                    self.saved = result
                    self.completed += 1
                    self.message = f"Session workspace saved: {result.path}"
                elif stamp == self._stamp and context == self._context:
                    restored, self.opened = result, result.path
                    self.completed += 1
                    failures = sum(
                        bool(file.message) and file.restored is None
                        for file in result.files
                    )
                    self.message = (
                        f"Session restored; {failures} source(s) need recovery. "
                        "Run analysis explicitly."
                    )
                else:
                    self.message = "Editor files changed; obsolete workspace ignored."
            except Exception as error:
                self.message = f"Session workspace failed: {error}"
        recovered: list[RestoredSessionFile] = []
        current = dict(stamp)
        for identity, (revision, future) in tuple(self._recoveries.items()):
            if identity not in current or current[identity] != revision:
                future.cancel()
                self._recoveries.pop(identity)
                self.message = "Source tab closed or changed; recovery abandoned."
            elif future.done():
                self._recoveries.pop(identity)
                try:
                    result = future.result()
                    recovered.append(result)
                    self.message = (
                        result.message or "Source restored with its saved recipe."
                    )
                except Exception as error:
                    self.message = f"Source recovery failed: {error}"
        return restored, tuple(recovered)

    def abandon(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None
        for _, future in self._recoveries.values():
            future.cancel()
        self._recoveries.clear()
        self.message = "Workspace results abandoned; executing work may still finish."

    def close(self) -> None:
        self.abandon()
        self._executor.shutdown(wait=False, cancel_futures=True)
