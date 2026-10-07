"""Application-owned file order, activation and shared worker lifetime."""

from dataclasses import replace
from pathlib import Path

from datelier.core.dataset import Dataset
from datelier.core.jobs import SharedWorkers
from datelier.gui.file_browser import FileBrowser
from datelier.gui.file_session import FileSession
from datelier.gui.workspace.capture import capture_session
from datelier.gui.workspace.preferences import PreferenceControls
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.inspection.comparisons.jobs import ComparisonJobs
from datelier.inspection.comparisons.types import (
    ComparisonSelection,
    PreparedComparison,
)
from datelier.inspection.text.comparisons.jobs import TextComparisonJobs
from datelier.inspection.text.comparisons.settings import TextComparisonSettings
from datelier.inspection.text.comparisons.types import (
    PreparedTextComparison,
    TextComparisonInput,
)
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.opening import OpeningJobs, OpeningRequest
from datelier.workspace.recent import RecentKind, RecentSource
from datelier.workspace.session_jobs import SessionJobs, SessionStamp
from datelier.workspace.session_restore import RestoredSession, SourceRecovery


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
        self.workspace_jobs = SessionJobs(self.workers)
        self.comparison_jobs = ComparisonJobs(executor=self.workers)
        self.comparisons: tuple[ComparisonSettings, ...] = ()
        self.text_comparisons: tuple[TextComparisonSettings, ...] = ()
        self.text_comparison_index = 0
        self.text_comparison_jobs = TextComparisonJobs(self.workers)
        self.order_reset = False
        self.pending_layout: tuple[str, tuple[str, ...]] | None = None
        self.workspace_path = ""
        self._whole_recent_serial = 0
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
        self._recent_files: dict[str, RecentSource] = {}
        self._recent_workspaces: dict[str, Path] = {}

    @property
    def active(self) -> FileSession:
        return next(file for file in self.files if file.identity == self.active_id)

    @property
    def file_sessions(self) -> tuple[FileSession, ...]:
        return tuple(
            file
            for owner in self.files
            for file in (owner, *owner.record_views.files, *owner.record_views.pending)
        )

    @property
    def datasets(self) -> dict[str, Dataset]:
        return {
            file.identity: file.loader.active.dataset
            for file in self.file_sessions
            if file.loader.active is not None
        }

    def select_comparison(
        self, result: PreparedComparison, series: int, bin_index: int
    ) -> None:
        source = result.series[series].origin
        dataset = self.datasets.get(source.file_id)
        if dataset is None:
            raise ValueError("The mapped file is unavailable")
        self.comparison_jobs.request_selection(result, series, bin_index, dataset)

    def text_comparison_inputs(
        self, recipe: TextComparisonSettings
    ) -> tuple[TextComparisonInput, ...]:
        files = {file.identity: file for file in self.file_sessions}
        inputs = []
        for source in recipe.sources:
            file = files.get(source.file_id)
            if file is None or file.loader.active is None:
                continue
            dataset = file.loader.active.dataset
            label = f"{dataset.source.path.name} {file.view_name} / {source.column}"
            inputs.append(
                TextComparisonInput(
                    source,
                    dataset,
                    label,
                    file.references.settings,
                    file.references.index,
                    tuple(sorted(file.selection.row_ids)),
                )
            )
        return tuple(inputs)

    def select_text_comparison(
        self, result: PreparedTextComparison, series: int, bin_index: int
    ) -> None:
        dataset = self.datasets.get(result.profiles[series].file_id)
        if dataset is None:
            raise ValueError("Mapped text source is unavailable")
        self.text_comparison_jobs.request_selection(result, series, bin_index, dataset)

    @property
    def source_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        for file in self.files:
            if file.loader.active is not None:
                paths.append(file.loader.active.dataset.source.path)
            if file.loader.status.path is not None:
                paths.append(file.loader.status.path)
            if file.workspace.jobs.issue is not None:
                paths.append(Path(file.workspace.jobs.issue.workspace.source.path))
            if file.recovery is not None:
                recipe, draft = file.recovery.file.recipe, file.recovery.file.draft
                if recipe is not None:
                    paths.append(Path(recipe.source.path))
                elif draft is not None:
                    paths.append(Path(draft.path))
        return tuple(dict.fromkeys(paths))

    @property
    def stamp(self) -> SessionStamp:
        return tuple(
            (
                file.identity,
                (file.loader.revision, file.loader.generation, file.editor.busy),
            )
            for owner in self.files
            for file in (owner, *owner.record_views.files, *owner.record_views.pending)
        )

    def save_workspace(
        self,
        path: Path,
        *,
        layout: str = "",
        hidden: tuple[str, ...] = (),
        overwrite: bool = False,
    ) -> None:
        self.workspace_jobs.request_save(
            path, capture_session(self, layout, hidden), overwrite=overwrite
        )
        self.workspace_path = str(path)

    def open_workspace(self, path: Path) -> None:
        self.opening.abandon()
        self.workspace_jobs.request_restore(
            path, self.stamp, context=self.opening.generation
        )
        self.workspace_path = str(path)

    def recover_source(
        self, identity: str, *, relink: Path | None = None, accept_changed: bool = False
    ) -> None:
        file = next(file for file in self.file_sessions if file.identity == identity)
        if file.recovery is None:
            raise ValueError("This file does not need source recovery")
        self.workspace_jobs.request_recovery(
            file.recovery,
            dict(self.stamp)[identity],
            SourceRecovery(identity, relink, accept_changed),
        )

    def prepare_records(self, identity: str) -> None:
        file = next(file for file in self.file_sessions if file.identity == identity)
        if file.deferred is None:
            raise ValueError("This view has no deferred array records")
        self.workspace_jobs.request_recovery(
            file.deferred,
            dict(self.stamp)[identity],
            SourceRecovery(identity, prepare_records=True),
        )

    def _install_session(self, restored: RestoredSession) -> None:
        self.comparison_jobs.clear()
        self.text_comparison_jobs.clear()
        self.browser.cancel()
        self.opening.abandon()
        for file in self.files:
            file.close()
        self._recent_files.clear()
        self._recent_workspaces.clear()
        self.files = []
        for result in restored.files:
            file = FileSession.create(self.preferences, executor=self.workers)
            file.identity = result.file.identity
            file.install_session_file(result)
            self.files.append(file)
            self._remember_file(file)
        self.comparisons = restored.workspace.comparisons
        self.text_comparisons = restored.workspace.text_comparisons
        self.text_comparison_index = restored.workspace.text_comparison_index
        self.pending_layout = (
            restored.workspace.layout,
            restored.workspace.hidden_windows,
        )
        self.activate(restored.workspace.active_id)
        self.order_reset = True
        self.workspace_path = str(restored.path)

    def open_recent(self, source: RecentSource) -> None:
        if source.source_kind == RecentKind.FILE:
            self.opening.request(
                (Path(source.path),),
                self.active_id,
                format=source.format,
                options=source.options,
                retry=True,
            )
            return
        self.open_workspace(Path(source.path))

    def _remember_file(self, file: FileSession) -> None:
        if file.loader.active is None:
            return
        imported = file.loader.active.imported
        entry = RecentSource(
            str(imported.dataset.source.path),
            format=imported.format,
            options=imported.options,
        )
        if self._recent_files.get(file.identity) != entry:
            self._recent_files[file.identity] = entry
            self.preferences.remember(entry)

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
        closed_ids = {
            f.identity
            for f in (file, *file.record_views.files, *file.record_views.pending)
        }
        file.close()
        self.text_comparisons = tuple(
            replace(
                recipe,
                sources=tuple(
                    source
                    for source in recipe.sources
                    if source.file_id not in closed_ids
                ),
            )
            for recipe in self.text_comparisons
        )
        self.comparisons = tuple(
            replace(
                recipe,
                sources=tuple(
                    source for source in recipe.sources if source.file_id != identity
                ),
            )
            for recipe in self.comparisons
        )
        self._recent_files.pop(identity, None)
        self._recent_workspaces.pop(identity, None)
        if self.browser.owner == identity:
            self.browser.cancel()
        if not self.files:
            self.new_tab()
        elif self.active_id == identity:
            self.activate(self.files[min(index, len(self.files) - 1)].identity)

    def reorder(self, identities: tuple[str, ...], *, native: bool = False) -> None:
        current = {file.identity: file for file in self.files}
        if len(identities) != len(current) or set(identities) != set(current):
            raise ValueError("Tab order must include every open file exactly once")
        self.files = [current[identity] for identity in identities]
        if not native:
            self.order_reset = True

    def poll(self) -> None:
        if self.closed:
            return
        for file in self.files:
            file.poll()
            self._remember_file(file)
            jobs = file.workspace.jobs
            path = jobs.saved.path if jobs.saved is not None else jobs.opened
            if path is not None and self._recent_workspaces.get(file.identity) != path:
                self._recent_workspaces[file.identity] = path
                self.preferences.remember(RecentSource(str(path), RecentKind.WORKSPACE))
        self.browser.poll()
        restored, recovered = self.workspace_jobs.poll(
            self.stamp, context=self.opening.generation
        )
        if restored is not None:
            self._install_session(restored)
        for result in recovered:
            file = next(
                file
                for file in self.file_sessions
                if file.identity == result.file.identity
            )
            file.install_session_file(result)
            self._remember_file(file)
        path = (
            self.workspace_jobs.saved.path
            if self.workspace_jobs.saved is not None
            else self.workspace_jobs.opened
        )
        if (
            path is not None
            and self.workspace_jobs.completed != self._whole_recent_serial
        ):
            self._whole_recent_serial = self.workspace_jobs.completed
            self.preferences.remember(RecentSource(str(path), RecentKind.WORKSPACE))
        for request, paths in self.opening.poll({file.identity for file in self.files}):
            self._open_resolved(request, paths)
        self.preferences.poll()
        known = {file.identity for file in self.file_sessions}
        self.text_comparisons = tuple(
            replace(
                recipe, sources=tuple(s for s in recipe.sources if s.file_id in known)
            )
            for recipe in self.text_comparisons
        )
        datasets = self.datasets
        self.comparison_jobs.sync(self.comparisons, datasets)
        recipe = (
            self.text_comparisons[
                min(self.text_comparison_index, len(self.text_comparisons) - 1)
            ]
            if self.text_comparisons
            else None
        )
        self.text_comparison_jobs.bind(
            recipe, self.text_comparison_inputs(recipe) if recipe else ()
        )
        for selection in (
            self.comparison_jobs.poll_selection(datasets),
            self.text_comparison_jobs.poll_selection(datasets),
        ):
            if selection is not None:
                self._apply_comparison_selection(selection)

    def _apply_comparison_selection(self, selection: ComparisonSelection) -> None:
        file = next(
            file
            for file in self.file_sessions
            if file.identity == selection.origin.file_id
        )
        if file.selection.choose(selection.origin.revision, selection.row_ids):
            owner = next(
                owner
                for owner in self.files
                if file is owner or file in owner.record_views.files
            )
            if file is not owner:
                owner.record_views.active_id = file.identity
            self.activate(owner.identity)
            if selection.first_position is not None:
                file.table.target_row = selection.first_position + 1
                file.table.jump = True

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
                    if request.format is not None and request.options is not None:
                        existing.controls.bind_settings(request.format, request.options)
                    existing.loader.request(
                        path, request.options, format=request.format
                    )
                self.activate(existing.identity)
                entry = self._recent_files.get(existing.identity)
                if entry is not None:
                    self.preferences.remember(entry)
                continue
            file = (
                owner
                if owner.loader.active is None
                and owner.loader.status.phase != LoadPhase.LOADING
                else self.new_tab()
            )
            file.controls.path = str(path)
            if request.format is not None and request.options is not None:
                file.controls.bind_settings(request.format, request.options)
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
        self.workspace_jobs.close()
        self.comparison_jobs.close()
        self.text_comparison_jobs.close()
        self.preferences.close()
        self.workers.shutdown(wait=True)
