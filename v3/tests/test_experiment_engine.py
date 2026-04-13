"""
Tests for v3.core.experiment_engine
"""

from __future__ import annotations

import threading
import time
import unittest

from v3.core.experiment_engine import (
    EngineState,
    EngineStateError,
    ExperimentEngine,
    StopRequested,
)
from v3.core.ui_events import UIEventBus


class TestEngineConstruction(unittest.TestCase):
    def test_initial_state_idle(self):
        engine = ExperimentEngine(UIEventBus())
        self.assertEqual(engine.state, EngineState.IDLE)
        self.assertTrue(engine.is_idle)
        self.assertFalse(engine.is_running)
        self.assertFalse(engine.is_paused)

    def test_initial_progress(self):
        engine = ExperimentEngine(UIEventBus())
        self.assertEqual(engine.current_line, 0)
        self.assertEqual(engine.total_lines, 0)
        self.assertEqual(engine.error_info, "")


class TestStartStop(unittest.TestCase):
    def setUp(self):
        self.bus = UIEventBus()
        self.engine = ExperimentEngine(self.bus)

    def test_start_transitions_to_running(self):
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(5)

        self.engine.start(task)
        entered.wait(timeout=2)
        self.assertEqual(self.engine.state, EngineState.RUNNING)
        self.assertTrue(self.engine.is_running)
        self.engine.request_stop()
        self.engine.join(timeout=2)

    def test_normal_completion_returns_to_idle(self):
        def task(eng):
            pass  # immediately finish

        self.engine.start(task)
        self.engine.join(timeout=2)
        self.assertEqual(self.engine.state, EngineState.IDLE)

    def test_start_when_running_raises(self):
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(5)

        self.engine.start(task)
        entered.wait(timeout=2)
        with self.assertRaises(EngineStateError):
            self.engine.start(task)
        self.engine.request_stop()
        self.engine.join(timeout=2)

    def test_request_stop_transitions_and_joins(self):
        entered = threading.Event()

        def task(eng):
            entered.set()
            while True:
                eng.check_stop()
                eng.interruptible_sleep(0.05)

        self.engine.start(task)
        entered.wait(timeout=2)
        self.engine.request_stop()
        self.assertTrue(self.engine.join(timeout=2))
        self.assertEqual(self.engine.state, EngineState.IDLE)

    def test_stop_from_idle_is_noop(self):
        self.engine.request_stop()
        self.assertEqual(self.engine.state, EngineState.IDLE)


class TestPauseResume(unittest.TestCase):
    def setUp(self):
        self.bus = UIEventBus()
        self.engine = ExperimentEngine(self.bus)

    def test_toggle_pause(self):
        entered = threading.Event()
        paused_reached = threading.Event()

        def task(eng):
            entered.set()
            for _ in range(100):
                eng.check_stop()
                eng.check_pause()
                if not paused_reached.is_set():
                    paused_reached.set()
                eng.interruptible_sleep(0.05)

        self.engine.start(task)
        entered.wait(timeout=2)

        self.engine.toggle_pause()
        self.assertEqual(self.engine.state, EngineState.PAUSED)
        self.assertTrue(self.engine.is_paused)

        self.engine.toggle_pause()
        self.assertEqual(self.engine.state, EngineState.RUNNING)
        self.assertFalse(self.engine.is_paused)

        self.engine.request_stop()
        self.engine.join(timeout=2)

    def test_stop_while_paused(self):
        entered = threading.Event()

        def task(eng):
            entered.set()
            while True:
                eng.check_stop()
                eng.check_pause()
                eng.interruptible_sleep(0.05)

        self.engine.start(task)
        entered.wait(timeout=2)

        self.engine.toggle_pause()
        self.assertEqual(self.engine.state, EngineState.PAUSED)

        self.engine.request_stop()
        self.assertTrue(self.engine.join(timeout=2))
        self.assertEqual(self.engine.state, EngineState.IDLE)

    def test_toggle_pause_when_idle_ignored(self):
        self.engine.toggle_pause()
        self.assertEqual(self.engine.state, EngineState.IDLE)


class TestCheckStop(unittest.TestCase):
    def test_check_stop_raises_when_set(self):
        engine = ExperimentEngine(UIEventBus())
        engine._stop_event.set()
        with self.assertRaises(StopRequested):
            engine.check_stop()

    def test_check_stop_ok_when_clear(self):
        engine = ExperimentEngine(UIEventBus())
        engine.check_stop()  # should not raise


class TestInterruptibleSleep(unittest.TestCase):
    def test_sleep_completes_normally(self):
        engine = ExperimentEngine(UIEventBus())

        def task(eng):
            eng.interruptible_sleep(0.05)

        engine.start(task)
        engine.join(timeout=2)
        self.assertEqual(engine.state, EngineState.IDLE)

    def test_sleep_interrupted_by_stop(self):
        engine = ExperimentEngine(UIEventBus())
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(60)  # long sleep

        engine.start(task)
        entered.wait(timeout=2)

        t0 = time.monotonic()
        engine.request_stop()
        engine.join(timeout=2)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 2.0, "Stop should interrupt sleep promptly")
        self.assertEqual(engine.state, EngineState.IDLE)

        def test_is_running_is_true_while_stopping(self):
            bus = UIEventBus()
            engine = ExperimentEngine(bus)
            entered = threading.Event()

            def task(eng):
                entered.set()
                eng.interruptible_sleep(60)

            engine.start(task)
            entered.wait(timeout=2)
            engine.request_stop()
            self.assertTrue(engine.is_running)
            engine.join(timeout=2)


class TestErrorState(unittest.TestCase):
    def setUp(self):
        self.bus = UIEventBus()
        self.engine = ExperimentEngine(self.bus)

    def test_exception_transitions_to_error(self):
        def task(eng):
            raise ValueError("instrument failure")

        self.engine.start(task)
        self.engine.join(timeout=2)
        self.assertEqual(self.engine.state, EngineState.ERROR)
        self.assertIn("instrument failure", self.engine.error_info)

    def test_reset_from_error_to_idle(self):
        def task(eng):
            raise RuntimeError("oops")

        self.engine.start(task)
        self.engine.join(timeout=2)
        self.assertEqual(self.engine.state, EngineState.ERROR)

        self.engine.reset()
        self.assertEqual(self.engine.state, EngineState.IDLE)
        self.assertEqual(self.engine.error_info, "")

    def test_reset_when_running_raises(self):
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(5)

        self.engine.start(task)
        entered.wait(timeout=2)
        with self.assertRaises(EngineStateError):
            self.engine.reset()
        self.engine.request_stop()
        self.engine.join(timeout=2)

    def test_request_stop_after_error_returns_to_idle(self):
        def task(eng):
            raise RuntimeError("fail then abort")

        self.engine.start(task)
        self.engine.join(timeout=2)
        self.assertEqual(self.engine.state, EngineState.ERROR)

        # Simulate user pressing Abort after the script already failed.
        self.engine.request_stop()
        self.assertEqual(self.engine.state, EngineState.IDLE)


class TestProgress(unittest.TestCase):
    def test_set_progress(self):
        engine = ExperimentEngine(UIEventBus())

        def task(eng):
            eng.set_progress(3, 10)

        engine.start(task)
        engine.join(timeout=2)
        self.assertEqual(engine.current_line, 3)
        self.assertEqual(engine.total_lines, 10)


class TestAbortCleanup(unittest.TestCase):
    def test_cleanup_called_on_stop(self):
        cleanup_called = threading.Event()

        def cleanup():
            cleanup_called.set()

        bus = UIEventBus()
        engine = ExperimentEngine(bus, on_abort_cleanup=cleanup)
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(60)

        engine.start(task)
        entered.wait(timeout=2)
        engine.request_stop()
        engine.join(timeout=2)
        self.assertTrue(cleanup_called.is_set())

    def test_cleanup_not_called_on_normal_completion(self):
        cleanup_called = threading.Event()

        def cleanup():
            cleanup_called.set()

        bus = UIEventBus()
        engine = ExperimentEngine(bus, on_abort_cleanup=cleanup)

        def task(eng):
            pass

        engine.start(task)
        engine.join(timeout=2)
        time.sleep(0.1)
        self.assertFalse(cleanup_called.is_set())

    def test_cleanup_failure_does_not_prevent_state_transition(self):
        def bad_cleanup():
            raise RuntimeError("cleanup failed")

        bus = UIEventBus()
        engine = ExperimentEngine(bus, on_abort_cleanup=bad_cleanup)
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(60)

        engine.start(task)
        entered.wait(timeout=2)
        engine.request_stop()
        engine.join(timeout=2)
        self.assertEqual(engine.state, EngineState.IDLE)


class TestJoin(unittest.TestCase):
    def test_join_when_no_worker(self):
        engine = ExperimentEngine(UIEventBus())
        self.assertTrue(engine.join(timeout=1))

    def test_join_timeout(self):
        engine = ExperimentEngine(UIEventBus())
        entered = threading.Event()

        def task(eng):
            entered.set()
            eng.interruptible_sleep(60)

        engine.start(task)
        entered.wait(timeout=2)
        result = engine.join(timeout=0.2)
        self.assertFalse(result)
        engine.request_stop()
        engine.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
