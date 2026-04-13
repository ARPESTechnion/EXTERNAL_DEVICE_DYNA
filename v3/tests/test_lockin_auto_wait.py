"""
Focused tests for SR830 auto-command completion polling behavior.
"""

from __future__ import annotations

import time
import unittest

from Utility.New_LockIn import LockInSR830
from Utility.New_Mock_LockIn import MockLockInSR830


class _FakeInstReadStbSequence:
    def __init__(self, values):
        self._values = list(values)
        self._idx = 0

    def read_stb(self):
        if self._idx >= len(self._values):
            return self._values[-1]
        value = self._values[self._idx]
        self._idx += 1
        return value


class _FakeInstNoReadStb:
    pass


class TestRealLockInAutoWait(unittest.TestCase):
    def test_wait_returns_when_ifc_becomes_idle(self):
        lockin = LockInSR830.__new__(LockInSR830)
        # IFC bit (bit 1) is clear while busy, then set when idle.
        lockin.inst = _FakeInstReadStbSequence([0, 0, 0b10])

        start = time.perf_counter()
        lockin._wait_for_command_complete(timeout_s=0.2, poll_interval_s=0.001)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.2)

    def test_wait_times_out_if_ifc_never_idle(self):
        lockin = LockInSR830.__new__(LockInSR830)
        lockin.inst = _FakeInstReadStbSequence([0])

        with self.assertRaises(TimeoutError):
            lockin._wait_for_command_complete(timeout_s=0.03, poll_interval_s=0.001)

    def test_serial_poll_falls_back_to_stb_query(self):
        lockin = LockInSR830.__new__(LockInSR830)
        lockin.inst = _FakeInstNoReadStb()
        lockin.query = lambda cmd, wait_after_write=0.0: "2"

        status = lockin.serial_poll_status()
        self.assertEqual(status, 2)

    def test_safe_auto_clears_buffer_after_completion(self):
        lockin = LockInSR830.__new__(LockInSR830)
        events = []

        lockin.write = lambda cmd: events.append(("write", cmd))
        lockin._wait_for_command_complete = (
            lambda timeout_s, poll_interval_s, consecutive_idle_polls:
            events.append(("wait", timeout_s, poll_interval_s, consecutive_idle_polls))
        )
        lockin._clear_buffer = lambda: events.append(("clear", None))

        lockin._safe_auto(
            "APHS",
            timeout_s=0.1,
            poll_interval_s=0.001,
            post_settle_s=0.0,
        )

        self.assertEqual(events[0], ("write", "APHS"))
        self.assertEqual(events[1][0], "wait")
        self.assertEqual(events[2], ("clear", None))


class TestMockLockInAutoWait(unittest.TestCase):
    def test_mock_auto_wait_finishes_quickly(self):
        lockin = MockLockInSR830()
        lockin._mock_auto_duration_s = 0.01

        start = time.perf_counter()
        lockin.safe_auto_phase(timeout_s=0.2)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.2)

    def test_mock_wait_times_out_when_forced_busy(self):
        lockin = MockLockInSR830()
        lockin._auto_busy_until = time.perf_counter() + 1.0

        with self.assertRaises(TimeoutError):
            lockin._wait_for_command_complete(timeout_s=0.02, poll_interval_s=0.001)


if __name__ == "__main__":
    unittest.main()
