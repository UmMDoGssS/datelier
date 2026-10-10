"""Independent tabs and explicit navigation with one bounded application pool."""

from dataclasses import replace
from pathlib import Path

from datelier.application.file import FileController
from datelier.application.navigation import WorkbenchNavigation
from datelier.core.jobs import SharedWorkers
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.io.loading import LoadPhase
from datelier.io.opening import OpeningJobs


class EditorController:
    def __init__(self) -> None:
        self.workers = SharedWorkers(workers=4)
        self.playback = AudioPlayback(executor=self.workers)
        self.opening = OpeningJobs(self.workers)
        self.navigation = WorkbenchNavigation()
        self.files: list[FileController] = []
        self.active_id = ""
        self.closed = False
        self.new_file()

    @property
    def active(self) -> FileController:
        return next(f for f in self.files if f.identity == self.active_id)

    def new_file(self, path: Path | None = None) -> FileController:
        if self.closed:
            raise RuntimeError("The editor is closed")
        file = FileController(self.workers, playback=self.playback)
        self.files.append(file)
        self.activate(file.identity)
        if path is not None:
            file.open(path)
        return file

    def activate(self, identity: str) -> None:
        if identity not in {f.identity for f in self.files}:
            raise ValueError("The file tab is unavailable")
        self.active_id = identity
        self.navigation.activate_file()
        for file in self.files:
            if file.identity != identity:
                file.audio.player.stop(file.identity)

    def choose_route(self, route: str) -> None:
        self.navigation.choose_canvas(comparison=route == "Compare files")
        if route != "Compare files":
            self.active.views = replace(self.active.views, tab=route)

    def open_paths(self, paths: tuple[Path, ...]) -> None:
        self.opening.request(paths, self.active_id)

    def close_file(self, identity: str) -> None:
        index = next(
            (i for i, f in enumerate(self.files) if f.identity == identity), None
        )
        if index is None:
            return
        file = self.files.pop(index)
        file.close()
        if not self.files:
            self.new_file()
        elif self.active_id == identity:
            self.activate(self.files[min(index, len(self.files) - 1)].identity)

    def reorder(self, identities: tuple[str, ...]) -> None:
        if len(identities) != len(self.files) or set(identities) != {
            f.identity for f in self.files
        }:
            raise ValueError("Tab order must include every file exactly once")
        files = {f.identity: f for f in self.files}
        self.files = [files[identity] for identity in identities]

    def poll(self) -> None:
        if self.closed:
            return
        for request, paths in self.opening.poll({f.identity for f in self.files}):
            for path in paths:
                existing = next(
                    (f for f in self.files if f.loader.status.path == path), None
                )
                if existing:
                    self.activate(existing.identity)
                    continue
                owner = next(f for f in self.files if f.identity == request.owner)
                file = (
                    owner
                    if owner.inspection is None
                    and owner.loader.status.phase != LoadPhase.LOADING
                    else self.new_file()
                )
                file.loader.request(path, request.options, format=request.format)
                self.activate(file.identity)
        for file in self.files:
            file.poll()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for file in self.files:
            file.close()
        self.opening.close()
        self.playback.close(wait=True)
        self.workers.shutdown(wait=True, cancel_futures=True)
