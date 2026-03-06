import time
import numpy as np
import pyvisa


class LockInSR830:
    """
    Safe, explicit SR830 lock-in amplifier driver via GPIB.
    Designed for transport measurements with current excitation.

    All commands follow the SR830 manual (Rev 2.6+).
    Key conventions:
      - OUTX i  sets the *communication interface* (0=RS232, 1=GPIB),
        NOT the sine output.  Never use it to toggle excitation.
      - The SR830 is not fully SCPI-compliant: its read buffer can
        hold stale data.  Every query goes through _clear_buffer()
        first to guarantee response alignment.
    """

    # ── Lookup tables (indices match the SR830 command parameters) ──

    # OFLT i → time constant value  (i = 0‥19)
    TAU_TABLE = [
        10e-6, 30e-6, 100e-6, 300e-6,       # i = 0–3
        1e-3,  3e-3,  10e-3,  30e-3,         # i = 4–7
        100e-3, 300e-3, 1, 3, 10, 30,        # i = 8–13
        100, 300, 1e3, 3e3, 1e4, 3e4         # i = 14–19
    ]

    # SENS i → full-scale sensitivity in volts  (i = 0‥26)
    SENS_TABLE = [
        2e-9,   5e-9,   10e-9,  20e-9,  50e-9,       # i = 0–4
        100e-9, 200e-9, 500e-9,                        # i = 5–7
        1e-6,   2e-6,   5e-6,                          # i = 8–10
        10e-6,  20e-6,  50e-6,                         # i = 11–13
        100e-6, 200e-6, 500e-6,                        # i = 14–16
        1e-3,   2e-3,   5e-3,                          # i = 17–19
        10e-3,  20e-3,  50e-3,                         # i = 20–22
        100e-3, 200e-3, 500e-3, 1.0                    # i = 23–26
    ]

    # OFSL i → number of time-constants needed for 99 % settling.
    # Standard values from SR830 app-note / cascade-filter theory:
    #   6 dB/oct (1 pole) → 5 τ,   12 dB → 7 τ,
    #  18 dB (3 poles)    → 9 τ,   24 dB → 12 τ
    FILTER_MULT = {0: 5, 1: 7, 2: 9, 3: 12}

    # ── Constructor ──────────────────────────────────────────────────

    def __init__(self, resource="GPIB0::8::INSTR"):
        """
        Open a VISA connection and verify we are talking to an SR830.

        Parameters
        ----------
        resource : str
            VISA resource string, e.g. "GPIB0::8::INSTR".
        """
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.inst.timeout = 5000           # 5 s default VISA timeout

        # First query after connection - force buffer clear
        idn = self.query("*IDN?", force_clear=True)
        if "SR830" not in idn:
            raise RuntimeError(f"Instrument is not SR830 (got: {idn})")

        self.initialize_default_state(reset=False)

    # ── Low-level VISA helpers ───────────────────────────────────────

    def write(self, cmd):
        """Send a command (no response expected)."""
        self.inst.write(cmd)

    def _clear_buffer(self):
        """
        Drain any stale bytes from the SR830 read buffer.

        The SR830 can leave old responses in the buffer after
        interrupted queries or auto-commands.  A short timeout
        ensures we never block when the buffer is already empty.
        """
        saved = self.inst.timeout
        try:
            self.inst.timeout = 50                  # 50 ms
            while True:
                self.inst.read()                    # discard leftovers
        except pyvisa.errors.VisaIOError:
            pass                                    # timeout → buffer empty
        finally:
            self.inst.timeout = saved

    def query(self, cmd, retries=2, wait_after_write=0.05, force_clear=False):
        """
        Synchronized query:  clear buffer → write → wait → read.

        Guarantees the response belongs to *this* command, preventing
        the classic SR830 buffer-desync problem.

        Parameters
        ----------
        cmd : str
            SCPI / SR830 command ending with '?'.
        retries : int
            Number of attempts before raising.
        wait_after_write : float
            Seconds to wait after write before reading (gives the
            SR830 time to prepare its response).
        force_clear : bool
            If True, always clear buffer before query. If False, only
            clear on first attempt or after errors (faster).
        """
        last_exc = None
        for attempt in range(retries):
            try:
                # Only clear buffer on first attempt or after retry
                if force_clear or attempt > 0:
                    self._clear_buffer()
                self.inst.write(cmd)
                time.sleep(wait_after_write)
                return self.inst.read().strip()
            except pyvisa.errors.VisaIOError as e:
                last_exc = e
                time.sleep(0.1 * (2 ** attempt))   # exponential back-off
                try:
                    self._clear_buffer()
                except Exception:
                    pass
        raise RuntimeError(
            f"VISA error on '{cmd}' after {retries} retries: {last_exc}"
        )

    # ── Default-state initialization ─────────────────────────────────

    def initialize_default_state(self, reset=False):
        """
        Reset to factory defaults, then configure for a typical
        transport-measurement setup.

        *RST does NOT change the communication interface, so GPIB
        stays active.

        Parameters
        ----------
        reset : bool
            If True, send *RST before applying settings.
        """
        if reset:
            self.write("*RST")
            time.sleep(0.5)            # allow reset to finish

        self.sine_output_off()         # SLVL → 4 mV (minimum)
        self.set_frequency(173)        # FREQ 173 Hz
        self.write("ISRC 1")          # Input config: A−B (differential)
        self.write("IGND 1")          # Input shield: grounded
        self.write("ICPL 0")          # Input coupling: AC
        self.write("FMOD 1")          # Reference source: internal
        self.write("SYNC 1")          # Sync filter: on
        self.set_time_constant(9)     # OFLT 9 → 300 ms
        self.set_filter_slope(3)      # OFSL 3 → 24 dB/oct
        self.reset_buffer()           # REST – clear data buffer

    # ── Reference / sine output ──────────────────────────────────────
    # IMPORTANT: OUTX sets the communication *interface* (0=RS232,
    # 1=GPIB).  The SR830 has NO sine-output on/off command.
    # To "disable" excitation, reduce SLVL to the 4 mV minimum.

    _MIN_SLVL = 0.004          # SR830 minimum sine amplitude (V rms)
    _MAX_SLVL = 5.0            # SR830 maximum sine amplitude (V rms)
    _SLVL_RES = 0.001          # 1 mV resolution

    def set_frequency(self, f):
        """FREQ f — set internal reference frequency (Hz)."""
        self.write(f"FREQ {f}")

    def get_frequency(self):
        """FREQ? — query reference frequency (Hz)."""
        return float(self.query("FREQ?"))

    def set_reference_amplitude(self, v):
        """SLVL v — set sine-out amplitude (V rms, 0.004–5.000)."""
        v = round(float(v) / self._SLVL_RES) * self._SLVL_RES
        v = max(self._MIN_SLVL, min(v, self._MAX_SLVL))
        self.write(f"SLVL {v}")

    def get_reference_amplitude(self):
        """SLVL? — query sine-out amplitude (V rms)."""
        return float(self.query("SLVL?"))

    def sine_output_on(self, amplitude_v):
        """Set sine output to the requested amplitude (V rms)."""
        self.set_reference_amplitude(amplitude_v)

    def sine_output_off(self):
        """Reduce sine output to the SR830 minimum (4 mV)."""
        self.set_reference_amplitude(self._MIN_SLVL)

    def set_excitation_current(self, current_rms, series_resistance):
        """
        Set excitation current by computing V = I × R_series.

        Parameters
        ----------
        current_rms : float   Target AC current (A rms).
        series_resistance : float   External series resistance (Ω).
        """
        if series_resistance <= 0:
            raise ValueError("Series resistance must be positive")
        voltage = current_rms * series_resistance
        if voltage > self._MAX_SLVL:
            raise ValueError(
                f"Required SLVL {voltage:.4f} V exceeds SR830 max "
                f"({self._MAX_SLVL} V).  Reduce current or resistance."
            )
        self.set_reference_amplitude(voltage)

    # ── Phase ────────────────────────────────────────────────────────

    def set_phase(self, deg):
        """PHAS deg — set reference phase shift (−360 to +730)."""
        self.write(f"PHAS {deg}")

    def get_phase(self):
        """PHAS? — query reference phase shift (degrees)."""
        return float(self.query("PHAS?"))

    # ── Sensitivity / time-constant / filter slope ───────────────────

    def set_sensitivity(self, idx):
        """SENS idx — set sensitivity (0‥26, see SENS_TABLE)."""
        if not 0 <= idx < len(self.SENS_TABLE):
            raise ValueError(
                f"Sensitivity index {idx} out of range 0‥{len(self.SENS_TABLE)-1}"
            )
        self.write(f"SENS {idx}")

    def get_sensitivity(self):
        """SENS? — query current sensitivity index."""
        return int(self.query("SENS?"))

    def set_time_constant(self, idx):
        """OFLT idx — set time constant (0‥19, see TAU_TABLE)."""
        if not 0 <= idx < len(self.TAU_TABLE):
            raise ValueError(
                f"Time-constant index {idx} out of range 0‥{len(self.TAU_TABLE)-1}"
            )
        self.write(f"OFLT {idx}")

    def get_time_constant(self):
        """OFLT? — query current time-constant index."""
        return int(self.query("OFLT?"))

    def set_filter_slope(self, idx):
        """OFSL idx — set low-pass filter slope (0=6, 1=12, 2=18, 3=24 dB/oct)."""
        if not 0 <= idx <= 3:
            raise ValueError(f"Filter-slope index {idx} out of range 0‥3")
        self.write(f"OFSL {idx}")

    def get_filter_slope(self):
        """OFSL? — query current filter-slope index."""
        return int(self.query("OFSL?"))

    # ── Data outputs ─────────────────────────────────────────────────

    def snap(self, *channels):
        """
        SNAP? — atomic simultaneous read of 2‥6 parameters.

        Valid channel codes (SR830 manual §5):
          1=X  2=Y  3=R  4=θ
          5=Aux In 1  6=Aux In 2  7=Aux In 3  8=Aux In 4
          9=Ref Freq  10=CH1 display  11=CH2 display
        """
        if len(channels) < 2 or len(channels) > 6:
            raise ValueError("SNAP requires 2–6 channel parameters")
        ch_str = ",".join(str(c) for c in channels)
        resp = self.query(f"SNAP? {ch_str}")
        return [float(x) for x in resp.split(",")]

    def read_x(self):
        """OUTP? 1 — read X output."""
        return float(self.query("OUTP? 1"))

    def read_y(self):
        """OUTP? 2 — read Y output."""
        return float(self.query("OUTP? 2"))

    def read_r(self):
        """OUTP? 3 — read R (magnitude) output."""
        return float(self.query("OUTP? 3"))

    def read_theta(self):
        """OUTP? 4 — read θ (phase) output."""
        return float(self.query("OUTP? 4"))

    # ── Data buffer ──────────────────────────────────────────────────

    def reset_buffer(self):
        """REST — reset the data buffer."""
        self.write("REST")

    # ── Status registers ─────────────────────────────────────────────
    #
    # SR830 Serial Poll Status Byte (*STB?):
    #   Bit 0  SCN   — 1 = no scan in progress
    #   Bit 1  IFC   — 1 = no internal command executing (IDLE)
    #   Bit 2  ERR   — 1 = command error has occurred
    #   Bit 3  LIA   — 1 = LIA status register has bits set
    #   Bit 4  MAV   — 1 = interface output buffer non-empty
    #   Bit 5  ESB   — 1 = event-status byte has bits set
    #   Bit 6  SRQ   — 1 = service request
    #   Bit 7         — unused
    #
    # LIA Status Byte (LIAS?):
    #   Bit 0  INPUT  — input/reserve overload
    #   Bit 1  FILTR  — time-constant filter overload
    #   Bit 2  OUTPUT — output overload
    #   Bit 3  UNLOCK — reference unlock
    #   Bit 4  RANGE  — detection frequency range changed
    #   Bit 5  TC     — time constant changed indirectly
    #   Bit 6  TRIG   — triggered
    #   Bit 7          — unused

    def serial_poll_status(self):
        """*STB? — read the serial poll status byte."""
        return int(self.query("*STB?"))

    def _wait_for_command_complete(self, timeout_s=30):
        """
        Simple wait for SR830 auto-commands (APHS/AGAN/ARSV).
        
        These typically complete in 2-5 seconds. We just wait a fixed
        time rather than polling, which matches the old driver behavior.
        """
        time.sleep(min(timeout_s, 5.0))  # Cap at 5s for typical auto-commands

    def is_overloaded(self):
        """
        Check the LIA status byte for input or output overload.

        Returns True if bit 0 (input/reserve overload) or bit 2
        (output overload) is set.
        """
        try:
            status = int(self.query("LIAS?"))
            return bool(status & 0b101)    # bit 0 | bit 2
        except Exception as e:
            print(f"Warning: could not read LIA status: {e}")
            return False

    # ── Safe auto-commands ───────────────────────────────────────────

    def _safe_auto(self, cmd, timeout_s=5.0):
        """
        Execute an auto-command (APHS / AGAN / ARSV), wait for it
        to finish, then clear buffer before next query.
        """
        self.write(cmd)
        self._wait_for_command_complete(timeout_s)
        self._clear_buffer()  # Clear any data left by auto-command

    def safe_auto_phase(self, timeout_s=5.0):
        """APHS — auto phase, then settle."""
        self._safe_auto("APHS", timeout_s)

    def safe_auto_gain(self, timeout_s=5.0):
        """AGAN — auto gain, then settle."""
        self._safe_auto("AGAN", timeout_s)

    def safe_auto_reserve(self, timeout_s=5.0):
        """ARSV — auto reserve, then settle."""
        self._safe_auto("ARSV", timeout_s)

    # ── Settling-time helpers ────────────────────────────────────────

    def estimate_settling_time(self, scale=1.0):
        """
        Estimate the time needed for the output to settle to 99 %
        of its final value, scaled by an optional factor.

        Formula:  t = FILTER_MULT[slope] × τ × scale

        FILTER_MULT contains the number of time-constants needed for
        99 % settling at each filter slope (see class docstring).
        Pass *scale* < 1.0 for a faster, less-accurate settle
        (e.g. 0.5 when you only need a rough reading).

        Parameters
        ----------
        scale : float
            Multiplier on the full 99 % settling time (default 1.0).
        """
        tau  = self.TAU_TABLE[self.get_time_constant()]
        mult = self.FILTER_MULT[self.get_filter_slope()]
        return mult * tau * scale

    def wait_for_settling(self, scale=1.0, show_timer=True):
        """Sleep for the estimated settling time (see estimate_settling_time)."""
        seconds = self.estimate_settling_time(scale)
        if show_timer:
            print(f"Settling for {seconds:.2f} s...")
        time.sleep(seconds)

    # ── Quick autorange ──────────────────────────────────────────────

    def quick_autorange(self, target_fraction=0.7, max_iter=20):
        """
        Adjust sensitivity so that R sits comfortably within the
        current full-scale range.

        Logic:
          1. If overloaded → step sensitivity coarser immediately
             (short fixed delay, NOT full settling).
          2. If R < margin × full-scale → range is good, settle and
             return.
          3. Otherwise → pick the tightest sensitivity that fits R
             and wait for a partial settle.

        Parameters
        ----------
        target_fraction : float
            Target fraction of full-scale for R (default 0.7 = 70 %).
        max_iter : int
            Safety limit to prevent infinite loops.
        """
        # First non-overload evaluation waits half-settle before using R.
        first_non_overload_seen = False

        for _ in range(max_iter):
            # ── Overload path: relieve fast, no full settling ──
            if self.is_overloaded():
                cur_idx = self.get_sensitivity()
                if cur_idx >= len(self.SENS_TABLE) - 1:
                    print("Warning: overload at maximum sensitivity range")
                    return
                self.set_sensitivity(cur_idx + 1)
                time.sleep(0.2)          # just enough for register update
                continue

            # ── Normal path: read and evaluate ──
            if not first_non_overload_seen:
                self.wait_for_settling(0.5)
                first_non_overload_seen = True

            r = abs(self.read_r())
            if r <= 0:
                return

            desired_fs = r / max(target_fraction, 1e-6)
            new_idx = next(
                (i for i, fs in enumerate(self.SENS_TABLE) if fs >= desired_fs),
                len(self.SENS_TABLE) - 1,
            )
            cur_idx = self.get_sensitivity()

            if new_idx == cur_idx:
                # Final half-settle: together with the earlier half-settle,
                # this gives a full settling interval on the final sensitivity.
                self.wait_for_settling(0.5)
                return

            self.set_sensitivity(new_idx)
            self.wait_for_settling(0.5)

        print("Warning: quick_autorange hit max iterations "
              f"({max_iter}), returning with current sensitivity")

    # ── High-level measurement ───────────────────────────────────────

    def measure(
        self,
        what=("X", "Y", "R", "Theta"),
        current=1e-6,
        series_resistance=10e3,
        avg=10,
        start_sens=10,
        use_autorange=True,
        use_autophase=True,
        sample_delay=0.05,
    ):
        """
        Perform a measurement: set excitation, auto-adjust, average
        multiple readings, then reduce excitation.

        Parameters
        ----------
        what : tuple of str
            Channels to read.  Valid: "X", "Y", "R", "Theta".
        current : float          Target excitation current (A rms).
        series_resistance : float  External series resistance (Ω).
        avg : int                Number of readings to average.
        start_sens : int         Initial sensitivity index.
        use_autorange : bool     Run quick_autorange before measuring.
        use_autophase : bool     Run safe_auto_phase before measuring.
        sample_delay : float     Delay between samples (seconds).

        Returns
        -------
        dict
            {"X": {"mean": …, "std": …}, …, "sens_idx": int}
        """
        # Valid SNAP channel codes for measurement quantities
        ch_map = {"X": 1, "Y": 2, "R": 3, "Theta": 4}
        for k in what:
            if k not in ch_map:
                raise ValueError(
                    f"Unknown channel '{k}'. Valid: {list(ch_map.keys())}"
                )

        start_time = time.perf_counter()

        if start_sens is not None:
            self.set_sensitivity(int(start_sens))
        self.set_excitation_current(current, series_resistance)
        self.reset_buffer()


        if use_autorange:
            self.quick_autorange()
            print("AutoRange")
        else:
            self.wait_for_settling(show_timer=True)
            
        if use_autophase:       
            self.safe_auto_phase()
            print("AutoPhase")

        # Acquire data
        data = {k: [] for k in what}
        for _ in range(avg):
            if len(what) == 1:
                key = what[0]
                if key == "X":
                    vals = [self.read_x()]
                elif key == "Y":
                    vals = [self.read_y()]
                elif key == "R":
                    vals = [self.read_r()]
                elif key == "Theta":
                    vals = [self.read_theta()]
                else:
                    raise ValueError(f"Unknown channel '{key}'")
            else:
                vals = self.snap(*[ch_map[k] for k in what])
            for k, v in zip(what, vals):
                data[k].append(v)
            time.sleep(sample_delay)

        self.sine_output_off()

        elapsed = time.perf_counter() - start_time
        print(f"Measurement complete in {elapsed:.2f} s")

        return {
            k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
            for k, v in data.items()
        } | {"sens_idx": self.get_sensitivity()}

    # ── Teardown ─────────────────────────────────────────────────────

    def close(self):
        """Close the VISA session and resource manager."""
        try:
            self.sine_output_off()
        except Exception:
            pass
        self.inst.close()
        self.rm.close()
