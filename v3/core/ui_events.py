"""
v3.core.ui_events  —  Thread-safe GUI update bus.

Worker threads post UIEvent objects to a queue.  The Tkinter main thread
drains the queue in its ``update_ui()`` tick and applies widget updates.

Design rules
------------
* **Fire-and-forget**: ``post()`` never blocks the caller.  If the queue
  is full the event is silently dropped (display updates are ephemeral).
* **Coalescing**: ``drain()`` returns only the *latest* value for each
  widget ID.  If 50 updates to ``"lockin_x"`` arrive between two ticks,
  only the last one is applied.
* **Widget IDs are constants** defined below — both producers and consumers
  import the same names so a typo becomes an ``ImportError``, not a
  silent mismatch.
"""

from __future__ import annotations

import queue
from typing import Any, NamedTuple

from v3.core.constants import UI_EVENT_QUEUE_CAPACITY


# ============================================================================
# UIEvent — the atom of cross-thread GUI communication
# ============================================================================
class UIEvent(NamedTuple):
    """A single widget update to be applied on the main thread."""
    widget_id: str
    value: Any


# ============================================================================
# UIEventBus
# ============================================================================
class UIEventBus:
    """
    Bounded queue of UIEvent objects with fire-and-forget posting and
    coalesced draining.

    Parameters
    ----------
    maxsize : int
        Queue capacity.  Default from ``UI_EVENT_QUEUE_CAPACITY``.
    """

    def __init__(self, maxsize: int = UI_EVENT_QUEUE_CAPACITY) -> None:
        self._queue: queue.Queue[UIEvent] = queue.Queue(maxsize=maxsize)
        self._dropped: int = 0

    # ------------------------------------------------------------------
    # Producer API  (called from ANY thread)
    # ------------------------------------------------------------------
    def post(self, widget_id: str, value: Any) -> None:
        """
        Enqueue a widget update.  Non-blocking — drops silently on overflow.
        """
        try:
            self._queue.put_nowait(UIEvent(widget_id, value))
        except queue.Full:
            self._dropped += 1

    def post_log(self, message: str) -> None:
        """Convenience: post a message to the system log panel."""
        self.post(W_LOG_MESSAGE, message)

    def post_dyna_log(self, message: str) -> None:
        """Convenience: post a message to the Dyna tab log."""
        self.post(W_DYNA_LOG_MESSAGE, message)

    # ------------------------------------------------------------------
    # Consumer API  (called from the MAIN / Tkinter thread only)
    # ------------------------------------------------------------------
    def drain(self) -> dict[str, Any]:
        """
        Drain all pending events and return the **latest** value per
        widget ID.  Returns ``{}`` if the queue is empty.
        """
        latest: dict[str, Any] = {}
        while True:
            try:
                evt = self._queue.get_nowait()
                latest[evt.widget_id] = evt.value
            except queue.Empty:
                break
        return latest

    @property
    def dropped_count(self) -> int:
        """Total number of events dropped due to queue overflow."""
        return self._dropped

    @property
    def pending(self) -> int:
        """Approximate number of events waiting to be drained."""
        return self._queue.qsize()


# ============================================================================
# Widget ID constants  —  one per updatable display element
# ============================================================================

# --- System / general ---
W_LOG_MESSAGE = "log_message"
W_SCRIPT_STATUS = "script_status"
W_SCRIPT_LINE = "script_line"
W_SCRIPT_STATE = "script_state"

# --- Dyna (PPMS) tab ---
W_DYNA_TEMP = "dyna_temp"
W_DYNA_TEMP_STATUS = "dyna_temp_status"
W_DYNA_FIELD = "dyna_field"
W_DYNA_FIELD_STATUS = "dyna_field_status"
W_DYNA_CHAMBER = "dyna_chamber"
W_DYNA_CHAMBER_STATUS = "dyna_chamber_status"
W_DYNA_CONNECTED = "dyna_connected"
W_DYNA_LOG_MESSAGE = "dyna_log_message"
W_DYNA_SETPOINT = "dyna_setpoint"

# --- Helmholtz tab ---
W_HELMHOLTZ_CURRENT_A = "helmholtz_current_a"
W_HELMHOLTZ_CURRENT_B = "helmholtz_current_b"
W_HELMHOLTZ_FIELD = "helmholtz_field"
W_HELMHOLTZ_RESISTANCE_A = "helmholtz_resistance_a"
W_HELMHOLTZ_RESISTANCE_B = "helmholtz_resistance_b"
W_HELMHOLTZ_CONNECTED = "helmholtz_connected"
W_HELMHOLTZ_RAMPING = "helmholtz_ramping"
W_HELMHOLTZ_SETPOINT = "helmholtz_setpoint"

# --- Lock-in tab ---
W_LOCKIN_X = "lockin_x"
W_LOCKIN_Y = "lockin_y"
W_LOCKIN_R = "lockin_r"
W_LOCKIN_PHASE = "lockin_phase"
W_LOCKIN_X_ERROR = "lockin_x_error"
W_LOCKIN_Y_ERROR = "lockin_y_error"
W_LOCKIN_R_ERROR = "lockin_r_error"
W_LOCKIN_PHASE_ERROR = "lockin_phase_error"
W_LOCKIN_SENSITIVITY = "lockin_sensitivity"
W_LOCKIN_RESISTANCE = "lockin_resistance"
W_LOCKIN_RESISTANCE_ERROR = "lockin_resistance_error"
W_LOCKIN_CHANNEL = "lockin_channel"
W_LOCKIN_STATUS = "lockin_status"
W_LOCKIN_CONNECTED = "lockin_connected"
W_LOCKIN_OUTPUT_VOLTAGE = "lockin_output_voltage"

# --- Hall bar (K2450) tab ---
W_HALL_RESULT = "hall_result"
W_HALL_CONNECTED = "hall_connected"
W_HALL_SOURCE_ENABLED = "hall_source_enabled"

# --- Strain (RP100 / AH2550A) tab ---
W_STRAIN_CONNECTED = "strain_connected"
W_STRAIN_STATUS = "strain_status"
W_STRAIN_VOLTAGE_CH1 = "strain_voltage_ch1"
W_STRAIN_VOLTAGE_CH2 = "strain_voltage_ch2"
W_STRAIN_CAPACITANCE = "strain_capacitance"
W_STRAIN_LOSS = "strain_loss"
W_STRAIN_FORCE = "strain_force"

# --- Switch tab ---
W_SWITCH_STATUS = "switch_status"
W_SWITCH_CONNECTED = "switch_connected"

# --- LED indicators ---
W_LED_LOCKIN = "led_lockin"
W_LED_HALL = "led_hall"
W_LED_SWITCH = "led_switch"
W_LED_HELMHOLTZ = "led_helmholtz"
W_LED_DYNA = "led_dyna"
W_LED_STRAIN = "led_strain"

# --- Results tab ---
W_RESULTS_NEW_POINT = "results_new_point"
W_IV_PROGRESS = "iv_progress"

# --- Connection status (generic) ---
W_INSTRUMENT_CONNECTED = "instrument_connected"
W_INSTRUMENT_DISCONNECTED = "instrument_disconnected"
W_INSTRUMENT_ERROR = "instrument_error"
