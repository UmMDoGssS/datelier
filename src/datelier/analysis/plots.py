"""Bounded embedding coordinates and column colors prepared off the GUI thread."""

from concurrent.futures import Executor, Future

from datelier.analysis.cluster_colors import prepare_cluster_colors
from datelier.analysis.types import ClusteringResult, EmbeddingResult
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.plotting.colors import prepare_colors
from datelier.plotting.data import Scatter, sample_indices


def prepare_embedding_plot(
    dataset: Dataset,
    result: EmbeddingResult,
    limit: int,
    color: str | None,
    clusters: ClusteringResult | None = None,
) -> Scatter:
    if dataset.revision != result.revision:
        raise ValueError("Embedding belongs to an obsolete dataset revision")
    if not 1 <= limit <= 10_000:
        raise ValueError("Displayed embedding limit must be 1–10,000")
    indices = sample_indices(len(result.row_ids), limit)
    coordinates = result.values[indices]
    positions = result.positions[indices]
    ids = result.row_ids[indices]
    x, y = coordinates[:, 0].copy(), coordinates[:, 1].copy()
    for array in (x, y, positions, ids):
        array.flags.writeable = False
    name = result.provenance.request.algorithm
    z = coordinates[:, 2].copy() if coordinates.shape[1] == 3 else None
    if z is not None:
        z.flags.writeable = False
    return Scatter(
        result.revision,
        f"{name} 1",
        f"{name} 2",
        x,
        y,
        ids,
        positions,
        len(result.row_ids),
        dataset.table.height,
        prepare_cluster_colors(dataset, positions, clusters)
        if clusters is not None
        else prepare_colors(dataset, positions, color)
        if color
        else None,
        z,
        f"{name} 3" if z is not None else "",
    )


class AnalysisPlots:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self.active: Scatter | None = None
        self.message = ""
        self._executor = JobExecutor(executor, max_workers=1, name="embedding")
        self._future: Future[Scatter] | None = None
        self._key: tuple[DatasetRevision, int, int, str | None, int] | None = None

    def ensure(
        self,
        dataset: Dataset,
        result: EmbeddingResult,
        limit: int,
        color: str | None,
        clusters: ClusteringResult | None = None,
    ) -> None:
        key = (dataset.revision, id(result), limit, color, id(clusters))
        if key == self._key:
            return
        if self._future is not None:
            self._future.cancel()
        self._key = key
        self.active = None
        self._future = self._executor.submit(
            prepare_embedding_plot, dataset, result, limit, color, clusters
        )
        self.message = "Preparing embedding plot…"

    def poll(self, revision: DatasetRevision | None) -> None:
        if self.active is not None and self.active.revision != revision:
            self.active = None
        future = self._future
        if future is None or not future.done():
            return
        self._future = None
        if self._key is None or self._key[0] != revision:
            return
        try:
            self.active = future.result()
            self.message = "Embedding plot ready."
        except Exception as error:
            self.message = f"Embedding plot failed: {error}"

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
