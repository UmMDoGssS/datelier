"""On-demand, revision-aware distribution preparation for one selected column."""

from concurrent.futures import Future, ThreadPoolExecutor

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.distributions import Comparison, DistributionSettings, prepare_comparison


class DistributionPreview:
    def __init__(self) -> None:
        self.active: Comparison | None = None
        self.message = ""
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="distribution"
        )
        self._future: Future[Comparison] | None = None
        self._key: tuple[DatasetRevision, DistributionSettings, int] | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def ensure(
        self, dataset: Dataset, settings: DistributionSettings, bins: int
    ) -> None:
        key = (dataset.revision, settings, bins)
        if key == self._key or self._closed:
            return
        settings.validate()
        self.clear()
        self._key = key
        self.message = "Preparing distribution…"
        self._future = self._executor.submit(
            prepare_comparison, dataset, settings, bins
        )

    def poll(self, revision: DatasetRevision | None) -> None:
        if self._key is not None and self._key[0] != revision:
            self.clear()
        future = self._future
        if future is None or not future.done():
            return
        self._future = None
        try:
            self.active = future.result()
            self.message = ""
        except Exception as error:
            self.message = f"Distribution unavailable: {error}"

    def clear(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._key = None
        self.active = None
        self.message = ""

    def close(self) -> None:
        self.clear()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
