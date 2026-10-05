"""Application-owned file order, activation and shared worker lifetime."""

from pathlib import Path

from datelier.core.jobs import SharedWorkers
from datelier.gui.file_browser import FileBrowser
from datelier.gui.file_session import FileSession
from datelier.gui.workspace.preferences import PreferenceControls
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.opening import OpeningJobs, OpeningRequest


class EditorSession:
    def __init__(
        self,
        preferences_path: Path | None = None,
        *,
        initial_path: Path | None = None,
        initial_workspace: Path | None = None,
        loader_override: DatasetLoader | None = None,
    ) -> None:
        self.workers = SharedWorkers()
        self.preferences = PreferenceControls(preferences_path, executor=self.workers)
        self.browser = FileBrowser(self.workers, Path.cwd())
        self.opening = OpeningJobs(self.workers)
        first = FileSession.create(
            self.preferences,
            executor=self.workers,
            source_path=initial_path,
            workspace_path=initial_workspace,
            loader_override=loader_override,
        )
        self.files = [first]
        self.active_id = first.identity
        self.focus_requested: str | None = first.identity
        self.closed = False

    @property
    def active(self) -> FileSession:
        return next(file for file in self.files if file.identity == self.active_id)

    def activate(self, identity: str, *, focus: bool = True) -> None:
        if not any(file.identity == identity for file in self.files):
            raise ValueError("That file tab is closed")
        self.active_id = identity
        if focus:
            self.focus_requested = identity

    def new_tab(self, source: Path | None = None) -> FileSession:
        if self.closed:
            raise RuntimeError("Editor is closed")
        file = FileSession.create(
            self.preferences, executor=self.workers, source_path=source
        )
        self.files.append(file)
        self.activate(file.identity)
        if source is not None:
            file.loader.request(source)
        return file

    def close_tab(self, identity: str) -> None:
        index = next(
            (i for i, file in enumerate(self.files) if file.identity == identity), None
        )
        if index is None:
            return
        file = self.files.pop(index)
        file.close()
        if self.browser.owner == identity:
            self.browser.cancel()
        if not self.files:
            self.new_tab()
        elif self.active_id == identity:
            self.activate(self.files[min(index, len(self.files) - 1)].identity)

    def reorder(self, identities: tuple[str, ...]) -> None:
        current = {file.identity: file for file in self.files}
        if len(identities) != len(current) or set(identities) != set(current):
            raise ValueError("Tab order must include every open file exactly once")
        self.files = [current[identity] for identity in identities]

    def poll(self) -> None:
        if self.closed:
            return
        for file in self.files:
            file.poll()
        self.browser.poll()
        for request, paths in self.opening.poll({file.identity for file in self.files}):
            self._open_resolved(request, paths)
        self.preferences.poll()

    def _open_resolved(self, request: OpeningRequest, paths: tuple[Path, ...]) -> None:
        owner = next(file for file in self.files if file.identity == request.owner)
        for path in paths:
            existing = next(
                (
                    file
                    for file in self.files
                    if file.loader.status.path == path
                    or file.loader.active is not None
                    and file.loader.active.dataset.source.path == path
                ),
                None,
            )
            if existing is not None:
                if (
                    request.retry
                    and existing is owner
                    and existing.loader.active is None
                    and existing.loader.status.phase
                    in (LoadPhase.FAILED, LoadPhase.ABANDONED)
                ):
                    existing.loader.request(
                        path, request.options, format=request.format
                    )
                self.activate(existing.identity)
                continue
            file = (
                owner
                if owner.loader.active is None
                and owner.loader.status.phase != LoadPhase.LOADING
                else self.new_tab()
            )
            file.controls.path = str(path)
            file.loader.request(path, request.options, format=request.format)
            self.activate(file.identity)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for file in self.files:
            file.close()
        self.browser.close()
        self.opening.close()
        self.preferences.close()
        self.workers.shutdown(wait=True)
