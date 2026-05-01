"""Integration tests for retire_worker (real QThread lifecycle).

These exercise the actual abort path: without retire_worker, dropping the
last Python reference to a still-running QThread triggers
``QThread::~QThread()`` -> ``qFatal`` -> ``abort()`` and the test process
dies. With it, the worker is parked in a list until ``run()`` returns.
"""

import time

from PyQt6.QtWidgets import QApplication

from myhondaplus_desktop.workers import ApiWorker, retire_worker

APP = QApplication.instance() or QApplication([])


def _pump_until(predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(0.01)
    return predicate()


def test_retiring_running_worker_does_not_abort_when_reference_dropped():
    def slow():
        time.sleep(0.3)
        return "ok"

    retired: list = []
    worker = ApiWorker(slow)
    worker.start()
    assert _pump_until(worker.isRunning, timeout_s=1.0)

    retire_worker(worker, retired)
    assert worker in retired

    # Local reference goes; only the retired list keeps the QThread alive.
    # If retire_worker is broken, the process aborts here once run() outlasts
    # the GC.
    del worker

    assert _pump_until(lambda: not retired, timeout_s=3.0), (
        "worker was not removed from retired list after run() returned")


def test_retired_worker_does_not_deliver_stale_results_to_ui():
    received: list = []

    def slow():
        time.sleep(0.2)
        return "stale"

    retired: list = []
    worker = ApiWorker(slow)
    worker.result_ready.connect(received.append)
    worker.start()
    assert _pump_until(worker.isRunning, timeout_s=1.0)

    retire_worker(worker, retired)
    assert _pump_until(lambda: not retired, timeout_s=3.0)

    assert received == []
