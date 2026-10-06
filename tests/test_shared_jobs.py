from threading import Event

import pytest

from datelier.core.jobs import JobExecutor, SharedWorkers


def test_closing_one_owner_cancels_its_queue_and_keeps_sibling_usable() -> None:
    workers = SharedWorkers(workers=1, capacity=4)
    first = JobExecutor(workers, max_workers=1, name="first")
    second = JobExecutor(workers, max_workers=1, name="second")
    started, release = Event(), Event()

    def blocked() -> int:
        started.set()
        assert release.wait(3)
        return 7

    try:
        executing = first.submit(blocked)
        assert started.wait(3)
        obsolete = first.submit(lambda: 99)
        current = second.submit(lambda: 12)
        first.shutdown(wait=False, cancel_futures=True)
        assert obsolete.cancelled()
        assert not executing.done()
        with pytest.raises(RuntimeError, match="closed"):
            first.submit(lambda: 1)
        release.set()
        assert executing.result(3) == 7
        assert current.result(3) == 12
        assert second.submit(lambda: 13).result(3) == 13
    finally:
        release.set()
        first.shutdown()
        second.shutdown()
        workers.shutdown()
    assert workers.pending == 0


def test_capacity_failure_is_visible_and_recoverable() -> None:
    workers = SharedWorkers(workers=1, capacity=1)
    release = Event()
    try:
        running = workers.submit(release.wait, 3)
        rejected = workers.submit(lambda: "unreachable")
        with pytest.raises(RuntimeError, match="Retry"):
            rejected.result(3)
        assert workers.pending == 1
        release.set()
        assert running.result(3)
        assert workers.submit(lambda: "retried").result(3) == "retried"
    finally:
        release.set()
        workers.shutdown()


def test_finished_and_failed_jobs_release_owner_bookkeeping() -> None:
    with SharedWorkers(workers=1) as workers:
        owner = JobExecutor(workers, max_workers=1, name="test")
        assert owner.submit(lambda: 5).result(3) == 5
        failure = owner.submit(lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            failure.result(3)
        owner.shutdown()
        assert workers.submit(lambda: 9).result(3) == 9


def test_visible_jobs_precede_queued_discovery_and_fifo_ties() -> None:
    workers = SharedWorkers(workers=1)
    started, release = Event(), Event()
    order: list[str] = []

    def blocked() -> None:
        started.set()
        assert release.wait(3)

    try:
        running = workers.submit(blocked)
        assert started.wait(3)
        index = JobExecutor(workers, max_workers=1, name="index", priority=10)
        visible = JobExecutor(workers, max_workers=1, name="visible", priority=-10)
        last = index.submit(order.append, "index")
        first = visible.submit(order.append, "visible")
        second = visible.submit(order.append, "selected")
        release.set()
        running.result(3)
        first.result(3)
        second.result(3)
        last.result(3)
        assert order == ["visible", "selected", "index"]
        index.shutdown()
        visible.shutdown()
    finally:
        release.set()
        workers.shutdown()
