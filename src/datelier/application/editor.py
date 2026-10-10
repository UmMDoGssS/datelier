"""Independent tabs and explicit navigation with one bounded application pool."""

from dataclasses import replace
from pathlib import Path

from datelier.application.browser import DirectoryController
from datelier.application.file import FileController
from datelier.application.navigation import WorkbenchNavigation
from datelier.application.preferences import PreferenceController
from datelier.application.settings_restore import restore_plots
from datelier.application.workspace import capture_session, install_file
from datelier.core.jobs import SharedWorkers
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.io.loading import LoadPhase
from datelier.io.opening import OpeningJobs
from datelier.workspace.recent import RecentKind, RecentSource
from datelier.workspace.session_jobs import SessionJobs, SessionStamp
from datelier.workspace.session_restore import SourceRecovery
from datelier.workspace.session_types import SessionFile, SessionWorkspace


class EditorController:
    def __init__(self, preferences_path: Path | None = None) -> None:
        self.workers = SharedWorkers(workers=4)
        self.playback = AudioPlayback(executor=self.workers)
        self.opening = OpeningJobs(self.workers)
        self.preferences = PreferenceController(preferences_path, self.workers)
        self.browser = DirectoryController(self.workers)
        self.workspace = SessionJobs(self.workers)
        self.pending_layout: tuple[str, tuple[str, ...], bool] | None = None
        self.notice = ""
        self._defaults_applied: set[str] = set()
        self._recent: dict[str, RecentSource] = {}
        self.navigation = WorkbenchNavigation()
        self.files: list[FileController] = []
        self.active_id = ""
        self.closed = False
        self.new_file()
        self.saved_session = SessionWorkspace(
            (SessionFile(self.active_id),), self.active_id
        )

    @property
    def active(self) -> FileController:
        return next(f for f in self.files if f.identity == self.active_id)

    @property
    def current(self) -> FileController:
        return self.active.record_views.active(self.active)

    @property
    def all_files(self) -> tuple[FileController, ...]:
        return tuple(
            file
            for owner in self.files
            for file in (owner, *owner.record_views.files, *owner.record_views.pending)
        )

    @property
    def stamp(self) -> SessionStamp:
        return tuple(
            (
                file.identity,
                (file.loader.revision, file.loader.generation, file.editor.busy),
            )
            for file in self.all_files
        )

    def save_workspace(
        self,
        path: Path,
        layout: str,
        hidden: tuple[str, ...],
        customized: bool,
        overwrite: bool,
    ) -> None:
        self.workspace.request_save(
            path, capture_session(self, layout, hidden, customized), overwrite=overwrite
        )

    def open_workspace(self, path: Path) -> None:
        self.workspace.request_restore(
            path, self.stamp, context=self.opening.generation
        )

    def recover(
        self,
        identity: str,
        path: Path | None,
        accept_changed: bool,
        prepare_records: bool = False,
    ) -> None:
        file = next(f for f in self.all_files if f.identity == identity)
        if file.recovery:
            self.workspace.request_recovery(
                file.recovery,
                dict(self.stamp)[identity],
                SourceRecovery(identity, path, accept_changed, prepare_records),
            )

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
            self.current.views = replace(self.current.views, tab=route)

    def open_paths(self, paths: tuple[Path, ...]) -> None:
        self.opening.request(paths, self.active_id)

    def open_recent(self, source: RecentSource) -> None:
        if source.source_kind == RecentKind.WORKSPACE:
            self.open_workspace(Path(source.path))
        else:
            self.opening.request(
                (Path(source.path),),
                self.active_id,
                format=source.format,
                options=source.options,
                retry=True,
            )

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
        self.preferences.poll()
        self.browser.poll()
        restored, recoveries = self.workspace.poll(
            self.stamp, context=self.opening.generation
        )
        if restored:
            for file in self.files:
                file.close()
            self.files = []
            for result in restored.files:
                file = FileController(
                    self.workers, identity=result.file.identity, playback=self.playback
                )
                install_file(file, result)
                self.files.append(file)
            self.active_id = restored.workspace.active_id
            self.saved_session = restored.workspace
            self.navigation.comparing = (
                restored.workspace.canvas_mode == "Compare files"
            )
            self.navigation.context_tab = restored.workspace.context_tab
            self.pending_layout = (
                restored.workspace.layout,
                restored.workspace.hidden_windows,
                restored.workspace.custom_layout,
            )
            self.notice = restored.notice
            self._defaults_applied.update(file.identity for file in self.all_files)
        for result in recoveries:
            file = next(f for f in self.all_files if f.identity == result.file.identity)
            install_file(file, result)
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
                file.open(path, request.options, format=request.format)
                self.activate(file.identity)
        for file in self.files:
            file.poll()
        if self.preferences.ready:
            for file in self.all_files:
                if file.identity not in self._defaults_applied:
                    defaults = self.preferences.value
                    if file.inspection:
                        restore_plots(
                            file.plots, file.inspection.dataset, defaults.plots
                        )
                        file.views = replace(
                            defaults.views,
                            references=replace(
                                defaults.views.references, roots=(), mappings=()
                            ),
                            array_slice=None,
                            checkpoint_slice=None,
                            tab=file.views.tab,
                        )
                        file.profiles.height = (
                            defaults.views.profile_height or file.profiles.height
                        )
                        file.profiles.mode = defaults.views.profile_mode
                        file.profiles.text = defaults.views.profile_text
                        file.profiles.selected = (
                            defaults.views.profile_selection or file.profiles.selected
                        )
                        self._defaults_applied.add(file.identity)
                if file.inspection:
                    imported = file.inspection.imported
                    entry = RecentSource(
                        str(imported.dataset.source.path),
                        RecentKind.FILE,
                        imported.format,
                        imported.options,
                    )
                    if self._recent.get(file.identity) != entry:
                        self.preferences.remember(entry)
                        self._recent[file.identity] = entry

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for file in self.files:
            file.close()
        self.workspace.close()
        self.browser.close()
        self.preferences.close()
        self.opening.close()
        self.playback.close(wait=True)
        # Feature owners already cancel their obsolete work. Drain storage cleanup
        # queued by those owners before joining the shared workers.
        self.workers.shutdown(wait=True, cancel_futures=False)
