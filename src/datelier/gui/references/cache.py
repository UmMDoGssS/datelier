"""One GUI-thread preview budget shared by Table and record gallery children."""

from datelier.gui.records.textures import TextureCache
from datelier.inspection.references.jobs import ReferenceJobs


class PreviewTextures(TextureCache):
    def __init__(self, jobs: ReferenceJobs) -> None:
        super().__init__()
        self.jobs = jobs
        self._scope: object = None

    def prepare(self) -> None:
        scope = self.jobs.revision, self.jobs.settings, id(self.jobs.index)
        if scope != self._scope:
            self._scope = scope
            self.invalidate()
        self.begin_frame()
