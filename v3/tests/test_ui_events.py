"""Tests for v3.core.ui_events."""

import threading
import time
import pytest

from v3.core.ui_events import UIEvent, UIEventBus, W_LOG_MESSAGE, W_LOCKIN_X


class TestUIEvent:
    def test_namedtuple_fields(self):
        evt = UIEvent("lockin_x", 1.234)
        assert evt.widget_id == "lockin_x"
        assert evt.value == 1.234

    def test_immutable(self):
        evt = UIEvent("lockin_x", 1.234)
        with pytest.raises(AttributeError):
            evt.widget_id = "other"


class TestUIEventBusPost:
    def test_post_single(self):
        bus = UIEventBus(maxsize=10)
        bus.post("w1", 42)
        assert bus.pending == 1

    def test_post_multiple(self):
        bus = UIEventBus(maxsize=10)
        for i in range(5):
            bus.post(f"w{i}", i)
        assert bus.pending == 5

    def test_post_drops_on_full(self):
        bus = UIEventBus(maxsize=3)
        for i in range(10):
            bus.post("w", i)
        assert bus.pending == 3
        assert bus.dropped_count == 7

    def test_post_log_convenience(self):
        bus = UIEventBus(maxsize=10)
        bus.post_log("hello")
        result = bus.drain()
        assert result[W_LOG_MESSAGE] == "hello"

    def test_post_dyna_log_convenience(self):
        bus = UIEventBus(maxsize=10)
        bus.post_dyna_log("dyna msg")
        result = bus.drain()
        assert "dyna_log_message" in result


class TestUIEventBusDrain:
    def test_drain_empty(self):
        bus = UIEventBus(maxsize=10)
        assert bus.drain() == {}

    def test_drain_returns_all(self):
        bus = UIEventBus(maxsize=100)
        bus.post("w1", "a")
        bus.post("w2", "b")
        bus.post("w3", "c")
        result = bus.drain()
        assert result == {"w1": "a", "w2": "b", "w3": "c"}

    def test_drain_coalesces_latest(self):
        """Multiple updates to the same widget → only the last value."""
        bus = UIEventBus(maxsize=100)
        bus.post("w1", 1)
        bus.post("w1", 2)
        bus.post("w1", 3)
        result = bus.drain()
        assert result == {"w1": 3}

    def test_drain_coalesces_mixed(self):
        bus = UIEventBus(maxsize=100)
        bus.post("w1", 1)
        bus.post("w2", "a")
        bus.post("w1", 2)
        bus.post("w2", "b")
        bus.post("w1", 3)
        result = bus.drain()
        assert result == {"w1": 3, "w2": "b"}

    def test_drain_clears_queue(self):
        bus = UIEventBus(maxsize=100)
        bus.post("w1", 1)
        bus.drain()
        assert bus.pending == 0
        assert bus.drain() == {}


class TestUIEventBusCrossThread:
    def test_producer_consumer(self):
        """Post from a worker thread, drain from the main thread."""
        bus = UIEventBus(maxsize=100)
        posted = []

        def producer():
            for i in range(50):
                bus.post(W_LOCKIN_X, i)
                posted.append(i)
                time.sleep(0.001)

        t = threading.Thread(target=producer)
        t.start()
        t.join()

        result = bus.drain()
        # Should have the latest value (49)
        assert result[W_LOCKIN_X] == 49

    def test_concurrent_posting(self):
        """Multiple producer threads posting simultaneously."""
        bus = UIEventBus(maxsize=5000)
        n_threads = 4
        n_posts = 200
        barrier = threading.Barrier(n_threads)

        def producer(tid):
            barrier.wait()
            for i in range(n_posts):
                bus.post(f"t{tid}", i)

        threads = [threading.Thread(target=producer, args=(tid,))
                    for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = bus.drain()
        # Each thread should have its latest value
        for tid in range(n_threads):
            assert f"t{tid}" in result
            # Value should be one of the posted values (order is nondeterministic
            # at the coalescing level, but it must be a valid value)
            assert 0 <= result[f"t{tid}"] < n_posts

    def test_no_events_lost_within_capacity(self):
        """If total events ≤ capacity, dropped_count stays 0."""
        bus = UIEventBus(maxsize=500)

        def producer():
            for i in range(100):
                bus.post(f"unique_{i}", i)

        t = threading.Thread(target=producer)
        t.start()
        t.join()

        assert bus.dropped_count == 0
        result = bus.drain()
        assert len(result) == 100
