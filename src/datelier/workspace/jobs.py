"""Background workspace save/restore with revision-aware publication."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass, replace
from pathlib import Path

from datelier.analysis.types import AnalysisRequest
from datelier.core.dataset import DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.exploration import PlotSettings
from datelier.io.types import ImportResult
from datelier.pipeline.history import Pipeline
from datelier.workspace.restore import RestoredWorkspace, SourceIssue, restore_workspace
from datelier.workspace.storage import reference_source, save_workspace
from datelier.workspace.types import Workspace, WorkspaceViews


@dataclass(frozen=True)
class SavedWorkspace:
    path: Path
    workspace: Workspace


class WorkspaceJobs:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self.message = "Save sources, recipes and views in a workspace."
        self.issue: SourceIssue | None = None
        self.saved: SavedWorkspace | None = None
        self._executor = JobExecutor(executor, max_workers=2, name="workspace")
        self._future: Future[RestoredWorkspace | SavedWorkspace] | None = None
        self._revision: DatasetRevision | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def request_restore(
        self,
        path: Path,
        revision: DatasetRevision | None,
        *,
        relink: Path | None = None,
        accept_changed: bool = False,
    ) -> None:
        if self._closed:
            raise ValueError("Workspace jobs are closed")
        self.abandon()
        self.issue = None
        self._revision = revision
        self._future = self._executor.submit(
            restore_workspace, path, relink=relink, accept_changed=accept_changed
        )
        self.message = "Checking source and restoring workspace…"

    def request_save(
        self,
        path: Path,
        pipeline: Pipeline,
        imported: ImportResult,
        analysis: tuple[AnalysisRequest, ...],
        plots: PlotSettings,
        views: WorkspaceViews,
        *,
        overwrite: bool = False,
    ) -> None:
        if self._closed or self.busy:
            raise ValueError("Saving requires idle workspace jobs")
        self.saved = None
        self.issue = None
        self._revision = pipeline.current.revision

        def work() -> SavedWorkspace:
            destination = path.expanduser().resolve()
            if destination.exists() and not overwrite:
                raise ValueError("Workspace exists; enable Replace existing workspace")
            workspace = Workspace(
                reference_source(pipeline.source.source),
                imported.format,
                imported.options,
                pipeline.history,
                pipeline.cursor,
                analysis,
                replace(plots, clusters=None),
                views,
            )
            save_workspace(destination, workspace)
            return SavedWorkspace(destination, workspace)

        self._future = self._executor.submit(work)
        self.message = "Saving workspace…"

    def poll(self, revision: DatasetRevision | None) -> RestoredWorkspace | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        try:
            result = future.result()
        except SourceIssue as error:
            if revision == self._revision:
                self.issue = error
                self.message = str(error)
            else:
                self.message = "Dataset changed; obsolete workspace ignored."
            return None
        except Exception as error:
            self.message = f"Workspace failed: {error}"
            return None
        if isinstance(result, SavedWorkspace):
            self.saved = result
            self.message = f"Workspace saved: {result.path}"
            return None
        if revision != self._revision:
            self.message = "Dataset changed; obsolete workspace ignored."
            return None
        self.message = (
            "Workspace restored. Analysis settings loaded; run ML explicitly."
        )
        return result

    def abandon(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None
            self.message = (
                "Workspace result abandoned; executing work may still finish."
            )
        self.issue = None

    def close(self) -> None:
        self.abandon()
        self._closed = True
        # An already requested save may finish; no abandoned restore can publish.
        self._executor.shutdown(wait=False, cancel_futures=True)
