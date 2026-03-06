import time
import numpy as np
import pyvisa


class LockInSR830:
    """
    Safe, explicit SR830 lock-in driver.
    Designed for transport measurements with current excitation.
    """

    # ---------- Tables ----------
    TAU_TABLE = [
        10e-6, 30e-6, 100e-6, 300e-6,
        1e-3, 3e-3, 10e-3, 30e-3,
        0.1, 0.3, 1, 3, 10, 30,
        100, 300, 1e3, 3e3, 1e4, 3e4
    ]

    SENS_TABLE = [
        2e-9, 5e-9, 10e-9, 20e-9, 50e-9,
        100e-9, 200e-9, 500e-9,
        1e-6, 2e-6, 5e-6,
        10e-6, 20e-6, 50e-6,
        100e-6, 200e-6, 500e-6,
        1e-3, 2e-3, 5e-3,
        10e-3, 20e-3, 50e-3,
        100e-3, 200e-3, 500e-3, 1.0
    ]

    FILTER_MULT = {0: 5, 1: 7, 2: 9, 3: 12}

    # ---------- Init ----------
    def __init__(self, resource):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.read_termination = "\n"
        self.inst.write_termination = "\n"
        self.inst.timeout = 5000

        if "SR830" not in self.query("*IDN?"):
            raise RuntimeError("Instrument is not SR830")

        self.initialize_default_state()

    # ---------- Low-level ----------
    def write(self, cmd):
        self.inst.write(cmd)

    def query(self, cmd):
        try:
            return self.inst.query(cmd).strip()
        except pyvisa.errors.VisaIOError as e:
            raise RuntimeError(f"VISA error on '{cmd}': {e}")

    # ---------- Initialization ----------
    def initialize_default_state(self):
        self.write("*RST")
        time.sleep(0.5)

        self.output_on(False)
        self.set_frequency(223)
        self.write("ISRC 1")     # A-B differential
        self.write("IGND 1")     # Grounded
        self.write("ICPL 0")     # AC coupling
        self.write("FMOD 1")     # Internal reference
        self.set_time_constant(9)  # 300 ms
        self.set_filter_slope(3)   # 24 dB/oct
        self.reset_buffer()

    # ---------- Reference ----------
    def set_frequency(self, f): self.write(f"FREQ {f}")
    def get_frequency(self): return float(self.query("FREQ?"))

    def set_reference_amplitude(self, v): self.write(f"SLVL {v}")
    def get_reference_amplitude(self): return float(self.query("SLVL?"))

    def output_on(self, enable): self.write(f"OUTX {1 if enable else 0}")

    def set_excitation_current(self, current_rms, series_resistance):
        """
        Sets excitation current via reference output.
        """
        if series_resistance <= 0:
            raise ValueError("Series resistance must be positive")
        self.set_reference_amplitude(current_rms * series_resistance)

    # ---------- Phase ----------
    def set_phase(self, deg): self.write(f"PHAS {deg}")
    def get_phase(self): return float(self.query("PHAS?"))

    # ---------- Sensitivity / Filters ----------
    def set_sensitivity(self, idx):
        if not 0 <= idx < len(self.SENS_TABLE):
            raise ValueError("Invalid sensitivity index")
        self.write(f"SENS {idx}")

    def get_sensitivity(self): return int(self.query("SENS?"))

    def set_time_constant(self, idx): self.write(f"OFLT {idx}")
    def get_time_constant(self): return int(self.query("OFLT?"))

    def set_filter_slope(self, idx): self.write(f"OFSL {idx}")
    def get_filter_slope(self): return int(self.query("OFSL?"))

    # ---------- Outputs ----------
    def snap(self, *channels):
        """
        Atomic multi-read.
        Channels:
        1=X, 2=Y, 3=R, 4=Theta, 9=Noise
        """
        resp = self.query(f"SNAP? {','.join(map(str, channels))}")
        return [float(x) for x in resp.split(",")]

    def read_x(self): return float(self.query("OUTP? 1"))
    def read_y(self): return float(self.query("OUTP? 2"))
    def read_r(self): return float(self.query("OUTP? 3"))
    def read_theta(self): return float(self.query("OUTP? 4"))
    def read_noise(self): return float(self.query("OUTP? 9"))

    # ---------- Buffer ----------
    def reset_buffer(self): self.write("REST")

    # ---------- Status ----------
    def serial_poll_status(self):
        return int(self.query("*STB?"))

    def _wait_for_command_complete(self):
        while self.serial_poll_status() & (1 << 1):
            time.sleep(0.05)

    def is_overloaded(self):
        """
        Checks overload bits (X/Y).
        """
        return bool(self.serial_poll_status() & (1 << 2))

    # ---------- Safe auto ----------
    def _safe_auto(self, cmd):
        self.write(cmd)
        self._wait_for_command_complete()
        self.wait_for_settling(0.99)

    def safe_auto_phase(self): self._safe_auto("APHS")
    def safe_auto_gain(self): self._safe_auto("AGAN")
    def safe_auto_reserve(self): self._safe_auto("ARSV")

    # ---------- Settling ----------
    def estimate_settling_time(self, fraction=0.99):
        tau = self.TAU_TABLE[self.get_time_constant()]
        mult = self.FILTER_MULT[self.get_filter_slope()]
        return mult * tau * fraction / 0.99

    def wait_for_settling(self, fraction=0.99):
        time.sleep(self.estimate_settling_time(fraction))

    # ---------- Quick autorange ----------
    def quick_autorange(self, margin=0.3):
        self.wait_for_settling(0.9)

        while True:
            if self.is_overloaded():
                self.set_sensitivity(
                    min(self.get_sensitivity() + 1, len(self.SENS_TABLE) - 1)
                )
                self.wait_for_settling(0.9)
                continue

            r = abs(self.read_r())
            fs = self.SENS_TABLE[self.get_sensitivity()]

            if r < margin * fs:
                self.wait_for_settling(0.99)
                return

            for i, fullscale in enumerate(self.SENS_TABLE):
                if r < margin * fullscale:
                    self.set_sensitivity(i)
                    self.wait_for_settling(0.9)
                    break

    # ---------- Measurement ----------
    def measure(
        self,
        what=("X", "Y", "R"),
        current=1e-6,
        series_resistance=10e3,
        avg=10,
        start_sens=10,
        use_autorange=True,
        use_autophase=True
    ):
        self.set_sensitivity(start_sens)
        self.set_excitation_current(current, series_resistance)
        self.reset_buffer()
        self.output_on(True)

        if use_autophase:
            self.safe_auto_phase()
        if use_autorange:
            self.quick_autorange()

        self.wait_for_settling()

        data = {k: [] for k in what}
        ch_map = {"X": 1, "Y": 2, "R": 3, "Theta": 4, "Noise": 9}

        for _ in range(avg):
            vals = self.snap(*[ch_map[k] for k in what])
            for k, v in zip(what, vals):
                data[k].append(v)
            time.sleep(0.05)

        self.output_on(False)

        return {
            k: {"mean": np.mean(v), "std": np.std(v)}
            for k, v in data.items()
        } | {"sens_idx": self.get_sensitivity()}

    def close(self):
        self.inst.close()
        self.rm.close()
