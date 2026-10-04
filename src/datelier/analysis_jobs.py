"""One owned spawned analysis worker; GUI polls without waiting for computation."""

import multiprocessing as mp
from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from multiprocessing.connection import Connection
from threading import Event
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_types import (
    Algorithm,
    AnalysisRequest,
    AnalysisResult,
    ClusteringResult,
    EmbeddingResult,
    PreparedInput,
)
from datelier.dataset import Dataset, DatasetRevision

Runner = Callable[[PreparedInput], AnalysisResult]


def _worker(prepared: PreparedInput, runner: Runner, connection: Connection) -> None:
    try:
        connection.send(runner(prepared))
    except Exception as error:
        connection.send(str(error))
    finally:
        connection.close()


class AnalysisJobs:
    def __init__(self, runner: Runner = run_analysis) -> None:
        self.results: dict[Algorithm, AnalysisResult] = {}
        self.latest: AnalysisResult | None = None
        self.message = "Select analysis features and explicitly run an algorithm."
        self.phase = "Idle"
        self._runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="analysis"
        )
        self._future: Future[AnalysisResult] | None = None
        self._cancel = Event()
        self._revision: DatasetRevision | None = None
        self._started = 0.0
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    @property
    def elapsed(self) -> float:
        return perf_counter() - self._started if self.busy else 0

    def request(self, dataset: Dataset, request: AnalysisRequest) -> None:
        if self._closed or self.busy:
            raise ValueError("Wait for the current analysis to finish or cancel it")
        request.validate()
        self._revision = dataset.revision
        self._cancel = Event()
        self._started = perf_counter()
        self.phase = "Preparing bounded inputs"
        self.message = f"Running {request.algorithm}…"
        self._future = self._executor.submit(
            self._execute, dataset, request, self._cancel
        )

    def _execute(
        self, dataset: Dataset, request: AnalysisRequest, cancel: Event
    ) -> AnalysisResult:
        prepared = prepare_input(dataset, request)
        if cancel.is_set():
            raise CancelledError()
        self.phase = "Starting analysis worker"
        context = mp.get_context("spawn")
        receiving, sending = context.Pipe(duplex=False)
        process = context.Process(
            target=_worker, args=(prepared, self._runner, sending), daemon=True
        )
        try:
            process.start()
            sending.close()
            self.phase = f"Loading libraries / fitting {request.algorithm}"
            while not receiving.poll(0.05):
                if cancel.is_set():
                    raise CancelledError()
                if not process.is_alive():
                    raise RuntimeError(f"Analysis worker exited ({process.exitcode})")
            result = receiving.recv()
            if cancel.is_set():
                raise CancelledError()
            if not isinstance(result, (EmbeddingResult, ClusteringResult)):
                raise RuntimeError(str(result))
            if (
                result.revision != dataset.revision
                or result.provenance.request != request
            ):
                raise RuntimeError(
                    "Analysis worker returned mismatched identity or settings"
                )
            arrays: list[
                NDArray[np.uint64] | NDArray[np.float64] | NDArray[np.int64]
            ] = [result.row_ids]
            if isinstance(result, EmbeddingResult):
                arrays.extend((result.values, result.positions))
            else:
                arrays.append(result.labels)
                if result.fit is not None:
                    fit = result.fit
                    arrays.extend(
                        (
                            fit.centers,
                            fit.model.magnitudes,
                            fit.model.medians,
                            fit.model.means,
                            fit.model.deviations,
                        )
                    )
            for array in arrays:
                array.flags.writeable = False
            return result
        finally:
            receiving.close()
            sending.close()
            if process.pid is not None:
                process.join(0.1)
                if process.is_alive():
                    process.terminate()
                    process.join(2)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()

    def cancel(self) -> None:
        if self.busy:
            self._cancel.set()
            self.message = (
                "Cancellation requested; waiting for preparation/worker to stop."
            )

    def poll(self, revision: DatasetRevision | None) -> bool:
        if self.latest is not None and self.latest.revision != revision:
            self.latest = None
        self.results = {
            key: value
            for key, value in self.results.items()
            if value.revision == revision
        }
        if self.busy and self._revision != revision:
            self.cancel()
        future = self._future
        if future is None or not future.done():
            return False
        self._future = None
        self.phase = "Idle"
        try:
            result = future.result()
        except CancelledError:
            self.message = "Analysis cancelled; worker has stopped."
            return False
        except Exception as error:
            self.message = f"Analysis failed: {error}"
            return False
        if self._cancel.is_set():
            # A cancel can arrive after worker completion but before the GUI
            # polls the finished future. The joined result must still be ignored.
            self.message = "Analysis cancelled; worker has stopped."
            return False
        if result.revision != revision:
            self.message = "Dataset changed; obsolete analysis ignored."
            return False
        self.latest = result
        self.results[result.provenance.request.algorithm] = result
        self.message = f"{result.provenance.request.algorithm} completed."
        return True

    def close(self) -> None:
        self.cancel()
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
