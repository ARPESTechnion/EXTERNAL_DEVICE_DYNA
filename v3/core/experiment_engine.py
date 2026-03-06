"""
v3.core.experiment_engine  —  Central state-machine for experiment execution.

Replaces V2's boolean flag approach (``script_running``, ``script_paused``)
with a proper state machine backed by ``threading.Event`` objects for
responsive stop/pause without busy-wait polling.

States
------
  IDLE  →  RUNNING  →  IDLE        (normal completion)
  IDLE  →  RUNNING  →  STOPPING → IDLE   (abort)
  RUNNING ↔  PAUSED                (toggle pause)
  any   →  ERROR   →  IDLE        (after reset)

The engine runs scripts on a single **worker thread**.  All instrument
calls go through :class:`InstrumentBus`.  GUI updates go through
:class:`UIEventBus`.  Data writes go through :class:`DataManager`.
"""

from __future__ import annotations

import enum
import logging
import threading
from typing import Callable

from v3.core.ui_events import (
    UIEventBus,
    W_SCRIPT_LINE,
    W_SCRIPT_STATE,
    W_SCRIPT_STATUS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Engine states
# ============================================================================
class EngineState(enum.Enum):
    """Possible states of the experiment engine."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


# ============================================================================
# Exceptions
# ============================================================================
class StopRequested(Exception):
    """Raised by ``check_stop()`` to unwind the call stack when the
    engine is stopping.  Caught by the worker thread loop."""


class EngineStateError(RuntimeError):
    """Raised when an operation is attempted in an invalid state."""


# ============================================================================
# ExperimentEngine
# ============================================================================
class ExperimentEngine:
    """
    State-machine that controls experiment execution.

    Parameters
    ----------
    ui_bus : UIEventBus
        For posting status updates to the GUI.
    on_abort_cleanup : callable, optional
        Called when the engine moves to STOPPING — should disable all
        instrument outputs (Helmholtz → 0, Hall → off, lock-in → off).
    """

    def __init__(
        self,
        ui_bus: UIEventBus,
        on_abort_cleanup: Callable[[], None] | None = None,
    ) -> None:
        self._ui_bus = ui_bus
        self._on_abort_cleanup = on_abort_cleanup

        # State
        self._state = EngineState.IDLE
        self._state_lock = threading.Lock()

        # Events — used for responsive waiting
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()           # initially NOT paused (set = go)

        # Worker thread
        self._worker: threading.Thread | None = None

        # Script tracking
        self._current_line: int = 0       # 1-indexed
        self._total_lines: int = 0
        self._error_info: str = ""

    # ------------------------------------------------------------------
    # Read-only public properties
    # ------------------------------------------------------------------
    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state in (EngineState.RUNNING, EngineState.PAUSED)

    @property
    def is_paused(self) -> bool:
        return self._state == EngineState.PAUSED

    @property
    def is_idle(self) -> bool:
        return self._state == EngineState.IDLE

    @property
    def stop_requested(self) -> bool:
        """True if a stop has been requested (but may not yet be IDLE)."""
        return self._stop_event.is_set()

    @property
    def current_line(self) -> int:
        return self._current_line

    @property
    def total_lines(self) -> int:
        return self._total_lines

    @property
    def error_info(self) -> str:
        return self._error_info

    @property
    def stop_event(self) -> threading.Event:
        """Expose read-only access to the stop event for external waiters."""
        return self._stop_event

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def _set_state(self, new: EngineState) -> None:
        old = self._state
        self._state = new
        logger.info("Engine state: %s → %s", old.value, new.value)
        self._ui_bus.post(W_SCRIPT_STATE, new.value)

    def start(self, target: Callable[["ExperimentEngine"], None]) -> None:
        """
        Begin execution on a worker thread.

        Parameters
        ----------
        target : callable(engine)
            The function to run.  Receives this engine instance so it
            can call ``check_stop()``, ``interruptible_sleep()``, etc.

        Raises
        ------
        EngineStateError
            If not currently IDLE.
        """
        with self._state_lock:
            if self._state != EngineState.IDLE:
                raise EngineStateError(
                    f"Cannot start: engine is {self._state.value}"
                )
            self._stop_event.clear()
            self._pause_event.set()       # not paused
            self._current_line = 0
            self._total_lines = 0
            self._error_info = ""
            self._set_state(EngineState.RUNNING)

        self._worker = threading.Thread(
            target=self._run_wrapper,
            args=(target,),
            name="v3-experiment-worker",
            daemon=True,
        )
        self._worker.start()

    def _run_wrapper(self, target: Callable[["ExperimentEngine"], None]) -> None:
        """Worker entry point — wraps target with error handling."""
        aborted = False
        failed = False
        try:
            target(self)
        except StopRequested:
            aborted = True
            logger.info("Script stopped by user.")
            self._ui_bus.post_log("Script aborted")
        except Exception as exc:  # noqa: BLE001
            failed = True
            self._error_info = str(exc)
            logger.exception("Script failed: %s", exc)
            self._ui_bus.post_log(f"ERROR: {exc}")
            with self._state_lock:
                self._set_state(EngineState.ERROR)
            return
        finally:
            # If stopping, run cleanup
            if self._stop_event.is_set() and self._on_abort_cleanup:
                try:
                    self._on_abort_cleanup()
                except Exception:  # noqa: BLE001
                    logger.exception("Abort cleanup failed")

        with self._state_lock:
            self._set_state(EngineState.IDLE)
            self._stop_event.clear()
            self._pause_event.set()
        if not aborted and not failed:
            self._ui_bus.post_log("Script completed.")

    # ------------------------------------------------------------------
    # Pause / resume
    # ------------------------------------------------------------------
    def toggle_pause(self) -> None:
        """Toggle pause state.  Only valid when RUNNING or PAUSED."""
        with self._state_lock:
            if self._state == EngineState.RUNNING:
                self._pause_event.clear()       # block interruptible_sleep
                self._set_state(EngineState.PAUSED)
                self._ui_bus.post_log("Script paused.")
            elif self._state == EngineState.PAUSED:
                self._pause_event.set()         # unblock
                self._set_state(EngineState.RUNNING)
                self._ui_bus.post_log("Script resumed.")
            else:
                logger.warning("toggle_pause ignored in state %s", self._state.value)

    # ------------------------------------------------------------------
    # Stop / abort
    # ------------------------------------------------------------------
    def request_stop(self) -> None:
        """
        Request a graceful stop.  The worker thread will raise
        ``StopRequested`` the next time it calls ``check_stop()``.
        """
        with self._state_lock:
            if self._state in (EngineState.IDLE, EngineState.STOPPING):
                return
            self._set_state(EngineState.STOPPING)
        self._stop_event.set()
        # If paused, unblock so the thread can exit
        self._pause_event.set()
        logger.info("Stop requested.")

    # ------------------------------------------------------------------
    # Worker-thread API  (called from the target function)
    # ------------------------------------------------------------------
    def check_stop(self) -> None:
        """
        Call this frequently from the worker function.  Raises
        ``StopRequested`` if the engine is stopping.
        """
        if self._stop_event.is_set():
            raise StopRequested()

    def check_pause(self) -> None:
        """
        Block until unpaused (or stopped).  Call between loop iterations.
        """
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                raise StopRequested()
            self._pause_event.wait(timeout=0.1)

    def interruptible_sleep(self, seconds: float) -> None:
        """
        Sleep for ``seconds``, waking early if stop is requested.

        Uses ``stop_event.wait()`` instead of ``time.sleep()`` so the
        worker responds within ~10 ms of a stop request.

        Raises
        ------
        StopRequested
            If stop is requested during the wait.
        """
        if self._stop_event.wait(timeout=seconds):
            raise StopRequested()

    def set_progress(
        self,
        line: int,
        total: int,
        loop_level: int = 0,
        parent_line: int = 0,
    ) -> None:
        """Update script progress (1-indexed)."""
        self._current_line = line
        self._total_lines = total
        self._ui_bus.post(W_SCRIPT_LINE, (line, total, loop_level, parent_line))
        self._ui_bus.post(W_SCRIPT_STATUS, f"Line {line}/{total}")

    # ------------------------------------------------------------------
    # Joining
    # ------------------------------------------------------------------
    def join(self, timeout: float = 5.0) -> bool:
        """
        Wait for the worker thread to finish.  Returns True if it
        terminated within the timeout.
        """
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=timeout)
            return not self._worker.is_alive()
        return True

    def reset(self) -> None:
        """
        Force the engine back to IDLE.  Only valid from ERROR state or
        after the worker has terminated.
        """
        with self._state_lock:
            if self._state == EngineState.ERROR or (
                self._worker is not None and not self._worker.is_alive()
            ):
                self._set_state(EngineState.IDLE)
                self._stop_event.clear()
                self._pause_event.set()
                self._error_info = ""
            else:
                raise EngineStateError(
                    f"Cannot reset: engine is {self._state.value} and worker alive."
                )
