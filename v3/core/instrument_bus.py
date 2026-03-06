"""
v3.core.instrument_bus  —  Thread-safe instrument access layer.

Every instrument call in the system goes through ``InstrumentBus``.
It provides:

* **Per-instrument locks** — different instruments can be used
  concurrently (e.g. dyna poller + lockin measurement).
* **Atomic execute()** — acquires lock, None-checks the instance,
  calls the method, and releases the lock.  Eliminates the V2
  TOCTOU race (``if inst is not None: inst.method()``).
* **acquire() context manager** — holds one instrument lock for
  a multi-call sequence (e.g. source-enable → measure → source-disable).
* **Deadlock guard** — a thread that already holds one instrument
  lock is prevented from acquiring a second one.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from v3.core.constants import ALL_INSTRUMENTS

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================
class InstrumentNotConnectedError(RuntimeError):
    """Raised when ``execute()`` or ``acquire()`` targets an instrument
    whose instance is ``None`` (not connected)."""


class InstrumentBusDeadlockError(RuntimeError):
    """Raised when a thread already holding one instrument lock tries to
    acquire a second one — this would risk deadlock."""


# ============================================================================
# InstrumentBus
# ============================================================================
class InstrumentBus:
    """
    Centralized, thread-safe registry for all instrument instances.

    Parameters
    ----------
    instrument_names : tuple[str, ...]
        Canonical names.  Default is ``ALL_INSTRUMENTS`` from constants.
    """

    def __init__(
        self,
        instrument_names: tuple[str, ...] = ALL_INSTRUMENTS,
    ) -> None:
        self._instruments: dict[str, Any | None] = {n: None for n in instrument_names}
        self._locks: dict[str, threading.Lock] = {n: threading.Lock() for n in instrument_names}
        # Per-thread tracking of currently-held lock name (deadlock guard)
        self._held: threading.local = threading.local()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _validate_name(self, name: str) -> None:
        if name not in self._instruments:
            raise KeyError(
                f"Unknown instrument '{name}'. "
                f"Valid names: {list(self._instruments.keys())}"
            )

    def _get_held(self) -> str | None:
        """Return the instrument name currently held by *this* thread, or None."""
        return getattr(self._held, "name", None)

    def _set_held(self, name: str | None) -> None:
        self._held.name = name

    # ------------------------------------------------------------------
    # Connection management  (called from ExperimentEngine thread)
    # ------------------------------------------------------------------
    def connect(self, name: str, instance: Any) -> None:
        """
        Register an instrument instance.  Thread-safe — acquires the
        instrument's lock before swapping the reference.
        """
        self._validate_name(name)
        with self._locks[name]:
            self._instruments[name] = instance
        logger.info("InstrumentBus: connected '%s'", name)

    def disconnect(self, name: str) -> Any | None:
        """
        Unregister an instrument instance.  Returns the old instance
        (so the caller can call its ``disconnect()`` or ``shutdown()``
        method).  Thread-safe.
        """
        self._validate_name(name)
        with self._locks[name]:
            old = self._instruments[name]
            self._instruments[name] = None
        logger.info("InstrumentBus: disconnected '%s'", name)
        return old

    def is_connected(self, name: str) -> bool:
        """Non-blocking connectivity check."""
        self._validate_name(name)
        return self._instruments[name] is not None

    # ------------------------------------------------------------------
    # Single-call access
    # ------------------------------------------------------------------
    def execute(
        self,
        name: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Thread-safe single method call on an instrument.

        Acquires the instrument lock, verifies the instance is not None,
        calls ``getattr(instance, method)(*args, **kwargs)``, and releases
        the lock.

        Raises
        ------
        InstrumentNotConnectedError
            If the instrument is ``None``.
        InstrumentBusDeadlockError
            If this thread already holds a *different* instrument lock.
        """
        self._validate_name(name)

        currently_held = self._get_held()
        if currently_held is not None and currently_held != name:
            raise InstrumentBusDeadlockError(
                f"Thread '{threading.current_thread().name}' already holds "
                f"'{currently_held}' — cannot acquire '{name}' (deadlock risk)."
            )

        # If we already hold this instrument's lock (re-entrant execute
        # inside an acquire() block), skip re-acquisition.
        if currently_held == name:
            inst = self._instruments[name]
            if inst is None:
                raise InstrumentNotConnectedError(
                    f"Instrument '{name}' is not connected."
                )
            return getattr(inst, method)(*args, **kwargs)

        with self._locks[name]:
            self._set_held(name)
            try:
                inst = self._instruments[name]
                if inst is None:
                    raise InstrumentNotConnectedError(
                        f"Instrument '{name}' is not connected."
                    )
                return getattr(inst, method)(*args, **kwargs)
            finally:
                self._set_held(None)

    # ------------------------------------------------------------------
    # Multi-call context manager
    # ------------------------------------------------------------------
    @contextmanager
    def acquire(self, name: str) -> Iterator[Any]:
        """
        Hold the instrument lock for a multi-call sequence.

        Usage::

            with bus.acquire("keithley2450") as k:
                k.source_current = 0.001
                k.enable_source()
                v = k.measure_voltage(...)
                k.disable_source()

        While inside the ``with`` block, ``execute(name, ...)`` calls
        for the **same** instrument are allowed (re-entrant) and do not
        re-acquire the lock.

        Raises
        ------
        InstrumentNotConnectedError
            If the instrument is ``None`` at entry.
        InstrumentBusDeadlockError
            If this thread already holds a *different* instrument lock.
        """
        self._validate_name(name)

        currently_held = self._get_held()
        if currently_held is not None and currently_held != name:
            raise InstrumentBusDeadlockError(
                f"Thread '{threading.current_thread().name}' already holds "
                f"'{currently_held}' — cannot acquire '{name}' (deadlock risk)."
            )
        if currently_held == name:
            # Already inside an acquire() for this instrument — yield directly.
            inst = self._instruments[name]
            if inst is None:
                raise InstrumentNotConnectedError(
                    f"Instrument '{name}' is not connected."
                )
            yield inst
            return

        with self._locks[name]:
            self._set_held(name)
            try:
                inst = self._instruments[name]
                if inst is None:
                    raise InstrumentNotConnectedError(
                        f"Instrument '{name}' is not connected."
                    )
                yield inst
            finally:
                self._set_held(None)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def connected_instruments(self) -> list[str]:
        """Return names of all currently-connected instruments."""
        return [n for n, inst in self._instruments.items() if inst is not None]

    def disconnect_all(self) -> dict[str, Any | None]:
        """
        Disconnect every instrument and return a dict of old instances.
        Used during shutdown.
        """
        old: dict[str, Any | None] = {}
        for name in self._instruments:
            old[name] = self.disconnect(name)
        return old

    def get_raw(self, name: str) -> Any | None:
        """
        Return the raw instrument reference **without** acquiring any lock.

        ONLY for read-only attribute access on immutable data (e.g.
        ``lockin.TAU_TABLE``).  Never use this to call instrument methods.
        """
        self._validate_name(name)
        return self._instruments[name]
