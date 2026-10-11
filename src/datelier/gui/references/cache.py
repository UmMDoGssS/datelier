"""One GUI-thread preview budget shared by Table and record gallery children."""

from collections.abc import Callable

from datelier.gui.records.media import TextureCache
from datelier.inspection.references.jobs import ReferenceJobs


class PreviewTextures(TextureCache):
    def __init__(
        self, jobs: ReferenceJobs, extra_scope: Callable[[], object] = lambda: None
    ) -> None:
        super().__init__()
        self.jobs = jobs
        self.extra_scope = extra_scope
        self._scope: object = None

    def prepare(self) -> None:
        scope = (
            self.jobs.revision,
            self.jobs.settings,
            id(self.jobs.index),
            self.extra_scope(),
        )
        if scope != self._scope:
            self._scope = scope
            self.invalidate()
        self.begin_frame()
