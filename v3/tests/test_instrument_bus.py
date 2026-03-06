"""Tests for v3.core.instrument_bus."""

import threading
import time
import pytest

from v3.core.instrument_bus import (
    InstrumentBus,
    InstrumentBusDeadlockError,
    InstrumentNotConnectedError,
)
from v3.core.constants import ALL_INSTRUMENTS


# ---------------------------------------------------------------------------
# Mock instrument for testing
# ---------------------------------------------------------------------------
class MockInstrument:
    """Minimal mock with identifiable calls."""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.calls: list[tuple[str, tuple, dict]] = []

    def get_value(self, channel: int = 0) -> float:
        self.calls.append(("get_value", (channel,), {}))
        return 42.0 + channel

    def set_value(self, value: float, channel: str = "a") -> None:
        self.calls.append(("set_value", (value, channel), {}))

    def query(self, cmd: str) -> str:
        self.calls.append(("query", (cmd,), {}))
        return f"response:{cmd}"

    def disconnect(self) -> None:
        self.calls.append(("disconnect", (), {}))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_default_instruments(self):
        bus = InstrumentBus()
        for name in ALL_INSTRUMENTS:
            assert not bus.is_connected(name)

    def test_custom_instruments(self):
        bus = InstrumentBus(instrument_names=("inst_a", "inst_b"))
        assert not bus.is_connected("inst_a")
        with pytest.raises(KeyError):
            bus.is_connected("unknown")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------
class TestConnection:
    def test_connect_and_is_connected(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        assert bus.is_connected("dev")

    def test_disconnect_returns_instance(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        old = bus.disconnect("dev")
        assert old is mock
        assert not bus.is_connected("dev")

    def test_disconnect_already_disconnected(self):
        bus = InstrumentBus(instrument_names=("dev",))
        old = bus.disconnect("dev")
        assert old is None

    def test_connect_invalid_name(self):
        bus = InstrumentBus(instrument_names=("dev",))
        with pytest.raises(KeyError):
            bus.connect("unknown", MockInstrument())

    def test_connected_instruments(self):
        bus = InstrumentBus(instrument_names=("a", "b", "c"))
        bus.connect("a", MockInstrument("a"))
        bus.connect("c", MockInstrument("c"))
        assert sorted(bus.connected_instruments()) == ["a", "c"]

    def test_disconnect_all(self):
        bus = InstrumentBus(instrument_names=("a", "b"))
        bus.connect("a", MockInstrument("a"))
        bus.connect("b", MockInstrument("b"))
        old = bus.disconnect_all()
        assert old["a"] is not None
        assert old["b"] is not None
        assert bus.connected_instruments() == []


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------
class TestExecute:
    def test_execute_basic(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        result = bus.execute("dev", "get_value", 3)
        assert result == 45.0
        assert mock.calls == [("get_value", (3,), {})]

    def test_execute_with_kwargs(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        bus.execute("dev", "set_value", 1.5, channel="b")
        assert mock.calls == [("set_value", (1.5, "b"), {})]

    def test_execute_not_connected_raises(self):
        bus = InstrumentBus(instrument_names=("dev",))
        with pytest.raises(InstrumentNotConnectedError):
            bus.execute("dev", "get_value")

    def test_execute_invalid_name_raises(self):
        bus = InstrumentBus(instrument_names=("dev",))
        with pytest.raises(KeyError):
            bus.execute("unknown", "get_value")

    def test_execute_method_not_found_raises(self):
        bus = InstrumentBus(instrument_names=("dev",))
        bus.connect("dev", MockInstrument())
        with pytest.raises(AttributeError):
            bus.execute("dev", "nonexistent_method")

    def test_execute_passes_return_value(self):
        bus = InstrumentBus(instrument_names=("dev",))
        bus.connect("dev", MockInstrument())
        result = bus.execute("dev", "query", "*IDN?")
        assert result == "response:*IDN?"


# ---------------------------------------------------------------------------
# acquire() context manager
# ---------------------------------------------------------------------------
class TestAcquire:
    def test_acquire_basic(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        with bus.acquire("dev") as inst:
            assert inst is mock
            inst.set_value(1.0)
            result = inst.get_value(0)
        assert len(mock.calls) == 2

    def test_acquire_not_connected_raises(self):
        bus = InstrumentBus(instrument_names=("dev",))
        with pytest.raises(InstrumentNotConnectedError):
            with bus.acquire("dev") as inst:
                pass

    def test_acquire_reentrant_execute(self):
        """execute() for the SAME instrument inside acquire() should work."""
        bus = InstrumentBus(instrument_names=("dev",))
        bus.connect("dev", MockInstrument())
        with bus.acquire("dev"):
            # This should NOT deadlock — reentrant for same instrument
            result = bus.execute("dev", "get_value", 5)
            assert result == 47.0

    def test_acquire_nested_same_instrument(self):
        """Nested acquire() for the SAME instrument should work."""
        bus = InstrumentBus(instrument_names=("dev",))
        bus.connect("dev", MockInstrument())
        with bus.acquire("dev") as inst1:
            with bus.acquire("dev") as inst2:
                assert inst1 is inst2


# ---------------------------------------------------------------------------
# Deadlock guard
# ---------------------------------------------------------------------------
class TestDeadlockGuard:
    def test_execute_different_instrument_while_holding_raises(self):
        """Cannot execute() on instrument B while acquire(A) is held."""
        bus = InstrumentBus(instrument_names=("a", "b"))
        bus.connect("a", MockInstrument("a"))
        bus.connect("b", MockInstrument("b"))
        with bus.acquire("a"):
            with pytest.raises(InstrumentBusDeadlockError):
                bus.execute("b", "get_value")

    def test_acquire_different_instrument_while_holding_raises(self):
        """Cannot acquire(B) while acquire(A) is held."""
        bus = InstrumentBus(instrument_names=("a", "b"))
        bus.connect("a", MockInstrument("a"))
        bus.connect("b", MockInstrument("b"))
        with bus.acquire("a"):
            with pytest.raises(InstrumentBusDeadlockError):
                with bus.acquire("b"):
                    pass


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------
class TestThreadSafety:
    def test_concurrent_execute_different_instruments(self):
        """Two threads accessing different instruments should not block."""
        bus = InstrumentBus(instrument_names=("a", "b"))
        mock_a = MockInstrument("a")
        mock_b = MockInstrument("b")
        bus.connect("a", mock_a)
        bus.connect("b", mock_b)

        results = {}
        barrier = threading.Barrier(2)

        def worker(name, result_key):
            barrier.wait()
            val = bus.execute(name, "get_value", 1)
            results[result_key] = val

        t1 = threading.Thread(target=worker, args=("a", "ra"))
        t2 = threading.Thread(target=worker, args=("b", "rb"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert results["ra"] == 43.0
        assert results["rb"] == 43.0

    def test_concurrent_execute_same_instrument_serialized(self):
        """Two threads accessing the SAME instrument must serialize."""
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)

        call_order: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def worker(tid):
            barrier.wait()
            for _ in range(10):
                bus.execute("dev", "get_value", 0)
                with lock:
                    call_order.append(tid)

        t1 = threading.Thread(target=worker, args=("t1",))
        t2 = threading.Thread(target=worker, args=("t2",))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both threads completed their 10 calls
        assert call_order.count("t1") == 10
        assert call_order.count("t2") == 10
        # Total calls on the mock = 20
        assert len(mock.calls) == 20

    def test_connect_during_execute(self):
        """Replacing an instrument while another thread is using it
        waits for the lock."""
        bus = InstrumentBus(instrument_names=("dev",))
        original = MockInstrument("original")
        replacement = MockInstrument("replacement")
        bus.connect("dev", original)

        connected_during_acquire = threading.Event()
        proceed = threading.Event()

        def holder():
            with bus.acquire("dev") as inst:
                connected_during_acquire.wait(timeout=5)
                # inst should still be 'original' because connect()
                # is waiting for this lock
                assert inst is original
                inst.get_value(0)
            proceed.set()

        def connector():
            time.sleep(0.05)  # let holder acquire first
            connected_during_acquire.set()
            bus.connect("dev", replacement)
            proceed.set()

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=connector)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # After both complete, the bus should have the replacement
        assert bus.is_connected("dev")
        with bus.acquire("dev") as inst:
            assert inst is replacement


# ---------------------------------------------------------------------------
# get_raw()
# ---------------------------------------------------------------------------
class TestGetRaw:
    def test_get_raw_returns_instance(self):
        bus = InstrumentBus(instrument_names=("dev",))
        mock = MockInstrument()
        bus.connect("dev", mock)
        assert bus.get_raw("dev") is mock

    def test_get_raw_returns_none_when_disconnected(self):
        bus = InstrumentBus(instrument_names=("dev",))
        assert bus.get_raw("dev") is None

    def test_get_raw_invalid_name(self):
        bus = InstrumentBus(instrument_names=("dev",))
        with pytest.raises(KeyError):
            bus.get_raw("nope")
