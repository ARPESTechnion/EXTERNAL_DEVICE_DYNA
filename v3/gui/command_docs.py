"""
v3.gui.command_docs  –  Structured documentation for every script DSL command.

Each entry in COMMAND_DOCS is a dict with:
  description : str          One-line summary of what the command does.
  positional   : list[dict]  Ordered positional args ({name, type, units, range, meaning}).
  kwargs       : list[dict]  Keyword args ({name, type, default, allowed, meaning}).
  example      : str         One or more realistic usage examples (newline-separated).

The preview renderer in results_tab._preview_selected_command() reads this dict
to produce formatted help text.
"""

from __future__ import annotations

_NA = ""  # "not applicable" sentinel for optional fields


def _kw(name: str, typ: str, default: str, allowed: str, meaning: str) -> dict:
    return {"name": name, "type": typ, "default": default, "allowed": allowed, "meaning": meaning}


def _pos(name: str, typ: str, units: str, rng: str, meaning: str) -> dict:
    return {"name": name, "type": typ, "units": units, "range": rng, "meaning": meaning}


COMMAND_DOCS: dict[str, dict] = {

    # ── General ─────────────────────────────────────────────────────────
    "test": {
        "description": "Sends a no-op 'test' event. Useful to verify the script engine is running.",
        "positional": [],
        "kwargs": [],
        "example": "test",
    },

    "initialize_data_file": {
        "description": (
            "Creates (or appends to) a CSV data file. "
            "If omitted, a timestamped file is created automatically."
        ),
        "positional": [],
        "kwargs": [
            _kw("directory", "str",  "data dir",     "any valid path", "Folder for the data file"),
            _kw("filename",  "str",  "auto-named",   "*.csv",          "Exact filename to use"),
            _kw("append",    "bool", "false",        "true/false",     "Append to an existing file instead of creating new"),
        ],
        "example": (
            "initialize_data_file\n"
            "initialize_data_file filename=my_run.csv\n"
            "initialize_data_file directory=C:/Data filename=sample_A.csv append=false"
        ),
    },

    "add_note": {
        "description": "Writes a free-text note into the data file as a comment row.",
        "positional": [
            _pos("text", "str", "", "any text (no quotes needed)", "The note to record"),
        ],
        "kwargs": [],
        "example": (
            "add_note Sample cooled to 10 K\n"
            "add_note Field sweep starting"
        ),
    },

    "run_saved_script": {
        "description": "Loads and runs another script file inline. Supports up to 8 levels of nesting.",
        "positional": [
            _pos("path", "str", "", "absolute path or filename", "Full path to the script file to execute"),
        ],
        "kwargs": [],
        "example": (
            "run_saved_script C:/Scripts/calibration.txt\n"
            "run_saved_script subscript.txt"
        ),
    },

    "set": {
        "description": "Defines a named numeric constant. Use $name later in args/kwargs with arithmetic.",
        "positional": [
            _pos("name", "identifier", "", "[A-Za-z_][A-Za-z0-9_]*", "Constant name"),
            _pos("expression", "numeric expr", "", "supports + - * / ( ) and $other_constants", "Value expression"),
        ],
        "kwargs": [],
        "example": (
            "SET points = 21\n"
            "SET span = 2000\n"
            "SET step = $span / ($points - 1)\n"
            "scan_dyna_field -1000 1000 $step 20 no_overshoot"
        ),
    },

    # ── Timing ──────────────────────────────────────────────────────────
    "wait_for": {
        "description": (
            "Waits until one or more instrument conditions are met, then adds an optional extra delay."
        ),
        "positional": [
            _pos("event(s)", "str", "", "temp, field, helmholtz, all, no_event", "Condition(s) to wait on (space-separated)"),
            _pos("extra_time", "float", "s", ">= 0", "Additional delay after condition is met"),
        ],
        "kwargs": [],
        "example": (
            "wait_for field 0\n"
            "wait_for temp 5\n"
            "wait_for temp field 10\n"
            "wait_for all 5\n"
            "wait_for no_event 2"
        ),
    },

    "time_sweep": {
        "description": "Runs its indented body repeatedly for a fixed total duration.",
        "positional": [
            _pos("sweep_time", "float", "s", "> 0", "Total duration to run the loop body"),
            _pos("time_gap",   "float", "s", ">= 0", "Pause between successive body executions"),
        ],
        "kwargs": [],
        "example": (
            "time_sweep 120 1\n"
            "  measure_hall_field\n"
            "\n"
            "time_sweep 300 0.5\n"
            "  measure_lockin avg=10"
        ),
    },

    "for_loop": {
        "description": "Repeats its indented body a fixed number of times. $loop_index (0-based) is available inside.",
        "positional": [
            _pos("iterations", "int", "", ">= 1  (or $var)", "Number of times to run the body"),
        ],
        "kwargs": [],
        "example": (
            "for_loop 10\n"
            "  measure_lockin avg=5\n"
            "\n"
            "SET n = 5\n"
            "for_loop $n\n"
            "  measure_hall_field current=1e-3"
        ),
    },

    "repeat": {
        "description": "Alias for for_loop. Repeats its indented body a fixed number of times.",
        "positional": [
            _pos("iterations", "int", "", ">= 1  (or $var)", "Number of times to run the body"),
        ],
        "kwargs": [],
        "example": (
            "repeat 5\n"
            "  measure_lockin avg=10\n"
            "END"
        ),
    },

    # ── PPMS ────────────────────────────────────────────────────────────
    "set_dyna_field": {
        "description": "Ramps the PPMS magnet to a target field and waits until it stabilises.",
        "positional": [
            _pos("field",    "float", "Oe",   "any",                             "Target field"),
            _pos("rate",     "float", "Oe/s", "> 0",                             "Ramp rate"),
            _pos("approach", "str",   "",     "linear / no_overshoot / oscillate","Magnet approach mode"),
        ],
        "kwargs": [],
        "example": (
            "set_dyna_field 1000 10 no_overshoot\n"
            "set_dyna_field -5000 50 linear"
        ),
    },

    "scan_dyna_field": {
        "description": "Steps the PPMS magnet from start to end in equal steps, running the indented body at each step.",
        "positional": [
            _pos("start",    "float", "Oe",   "any",                              "First field value"),
            _pos("end",      "float", "Oe",   "any",                              "Last field value"),
            _pos("step",     "float", "Oe",   "> 0",                              "Step size"),
            _pos("rate",     "float", "Oe/s", "> 0",                              "Ramp rate"),
            _pos("approach", "str",   "",     "linear / no_overshoot / oscillate", "Approach mode"),
        ],
        "kwargs": [],
        "example": (
            "scan_dyna_field -5000 5000 500 50 no_overshoot\n"
            "  measure_hall_field current=2e-3"
        ),
    },

    "sweep_dyna_field": {
        "description": "Continuously sweeps the PPMS field from start to end (linear, no step setpoints), running the body during the ramp.",
        "positional": [
            _pos("start", "float", "Oe",   "any", "Start field"),
            _pos("end",   "float", "Oe",   "any", "End field"),
            _pos("rate",  "float", "Oe/s", "> 0", "Sweep rate"),
        ],
        "kwargs": [
            _kw("gap_time", "float", "0", ">= 0", "Pause (s) between body executions during sweep"),
        ],
        "example": (
            "sweep_dyna_field -1000 1000 20 gap_time=0\n"
            "  measure_lockin avg=5"
        ),
    },

    "set_dyna_temp": {
        "description": "Ramps the PPMS temperature to a target value and waits until stable.",
        "positional": [
            _pos("temp",     "float", "K",    "> 0",                         "Target temperature"),
            _pos("rate",     "float", "K/min","0.1–20",                      "Ramp rate"),
            _pos("approach", "str",   "",     "fast_settle / fast / no_overshoot", "Stabilisation mode"),
        ],
        "kwargs": [],
        "example": (
            "set_dyna_temp 300 5 no_overshoot\n"
            "set_dyna_temp 10 2 fast_settle"
        ),
    },

    "scan_dyna_temp": {
        "description": "Steps the PPMS temperature from start to end, running the body at each step.",
        "positional": [
            _pos("start",    "float", "K",    "> 0",                         "First temperature"),
            _pos("end",      "float", "K",    "> 0",                         "Last temperature"),
            _pos("step",     "float", "K",    "> 0",                         "Step size"),
            _pos("rate",     "float", "K/min","0.1–20",                      "Ramp rate"),
            _pos("approach", "str",   "",     "fast_settle / fast / no_overshoot", "Approach mode"),
        ],
        "kwargs": [],
        "example": (
            "scan_dyna_temp 10 300 20 5 no_overshoot\n"
            "  measure_hall_field"
        ),
    },

    "sweep_dyna_temp": {
        "description": "Continuously sweeps the PPMS temperature, running the body during the ramp.",
        "positional": [
            _pos("start", "float", "K",    "> 0", "Start temperature"),
            _pos("end",   "float", "K",    "> 0", "End temperature"),
            _pos("rate",  "float", "K/min","0.1–20","Sweep rate"),
        ],
        "kwargs": [
            _kw("gap_time", "float", "0", ">= 0", "Pause (s) between body executions"),
        ],
        "example": (
            "sweep_dyna_temp 10 300 5 gap_time=3\n"
            "  measure_lockin avg=5"
        ),
    },

    # ── Helmholtz ────────────────────────────────────────────────────────
    "set_helmholtz_field": {
        "description": "Ramps the Helmholtz coil to a target field and waits until done.",
        "positional": [
            _pos("field", "float", "G (Oe)", "any", "Target field"),
            _pos("rate",  "float", "mA/s",   "> 0", "Current ramp rate"),
        ],
        "kwargs": [],
        "example": (
            "set_helmholtz_field 100 5.0\n"
            "set_helmholtz_field -200 10"
        ),
    },

    "apply_strain": {
        "description": (
            "Applies a pair of RP100 voltages, checks them against the current temperature limit, "
            "then reads capacitance, loss, and derived force from the AH2550A."
        ),
        "positional": [
            _pos("ch1_voltage", "float", "V", "any", "Voltage applied to RP100 channel 1"),
            _pos("ch2_voltage", "float", "V", "any", "Voltage applied to RP100 channel 2"),
        ],
        "kwargs": [
            _kw("dwell_s", "float", "10", ">= 0", "Wait after setting the voltages before reading the bridge"),
        ],
        "example": (
            "apply_strain 12 -12\n"
            "apply_strain 20 -20 dwell_s=5"
        ),
    },

    "scan_strain_voltage": {
        "description": (
            "Scans a strain-voltage range and runs the indented body at each generated voltage pair. "
            "The helper uses generate_voltage_list(v0, vf, step)."
        ),
        "positional": [
            _pos("start", "float", "V", "any", "First voltage used for the generated ch1/ch2 pairs"),
            _pos("end", "float", "V", "any", "Last voltage used for the generated ch1/ch2 pairs"),
            _pos("step", "float", "V", "> 0", "Step size used by generate_voltage_list"),
        ],
        "kwargs": [
            _kw("dwell_s", "float", "10", ">= 0", "Wait after each applied strain pair before reading"),
        ],
        "example": (
            "scan_strain_voltage 0 20 2\n"
            "  measure_lockin avg=10"
        ),
    },

    "scan_helmholtz_field": {
        "description": "Steps the Helmholtz field from start to end, running the body at each step.",
        "positional": [
            _pos("start", "float", "G", "any", "First field value"),
            _pos("end",   "float", "G", "any", "Last field value"),
            _pos("step",  "float", "G", "> 0", "Step size"),
            _pos("rate",  "float", "mA/s", "> 0", "Ramp rate"),
        ],
        "kwargs": [],
        "example": (
            "scan_helmholtz_field -300 300 30 5\n"
            "  measure_lockin avg=10"
        ),
    },

    "sweep_helmholtz_field": {
        "description": "Continuously sweeps the Helmholtz field, running the body during the ramp.",
        "positional": [
            _pos("start", "float", "G", "any", "Start field"),
            _pos("end",   "float", "G", "any", "End field"),
            _pos("rate",  "float", "mA/s", "> 0", "Sweep rate"),
        ],
        "kwargs": [
            _kw("gap_time", "float", "0", ">= 0", "Pause (s) between body executions"),
        ],
        "example": (
            "sweep_helmholtz_field -300 300 10 gap_time=0\n"
            "  measure_lockin avg=5"
        ),
    },

    # ── Hall / K2450 ────────────────────────────────────────────────────
    "enable_hall_output": {
        "description": "Turns on the K2450 current source (Hall-bar excitation).",
        "positional": [],
        "kwargs": [
            _kw("current",      "float", "1e-3", "A, any",  "Source current in amps"),
            _kw("compliance_v", "float", "10.0", "V, > 0",  "Voltage compliance limit"),
        ],
        "example": (
            "enable_hall_output current=2e-3 compliance_v=5"
        ),
    },

    "disable_hall_output": {
        "description": "Turns off the K2450 current source.",
        "positional": [],
        "kwargs": [],
        "example": "disable_hall_output",
    },

    "measure_hall_field": {
        "description": (
            "Sources a fixed DC current via the K2450 and measures voltage to derive "
            "Hall resistance / field. Records one data point."
        ),
        "positional": [],
        "kwargs": [
            _kw("current",       "float", "1e-3",  "A, any",         "Source current"),
            _kw("nplc",          "float", "10",    "0.001–10",       "Integration time in power-line cycles"),
            _kw("compliance_v",  "float", "10.0",  "V, > 0",         "Voltage compliance limit"),
            _kw("voltage_range", "float", "auto",  "V / mV / 'auto'","Sense voltage range (0 or 'auto' = auto-range)"),
            _kw("filter_count",  "int",   "10",    "1–100",          "Hardware averaging filter depth"),
            _kw("tbm",           "float", "0",     ">= 0 s",         "Time Between Measurements delay before reading"),
        ],
        "example": (
            "measure_hall_field\n"
            "measure_hall_field current=2e-3 nplc=10\n"
            "measure_hall_field current=1.5e-3 filter_count=20 voltage_range=1V"
        ),
    },

    "continuous_measure_hall_field": {
        "description": (
            "Like measure_hall_field but runs continuously (used inside time_sweep / for_loop). "
            "Keeps the source enabled between measurements for speed."
        ),
        "positional": [],
        "kwargs": [
            _kw("current",       "float", "1e-3",  "A, any",         "Source current"),
            _kw("nplc",          "float", "10",    "0.001–10",       "Integration cycles"),
            _kw("compliance_v",  "float", "10.0",  "V, > 0",         "Compliance limit"),
            _kw("voltage_range", "float", "auto",  "V / mV / 'auto'","Sense range"),
            _kw("filter_count",  "int",   "10",    "1–100",          "Averaging filter depth"),
            _kw("tbm",           "float", "0",     ">= 0 s",         "Delay before reading"),
        ],
        "example": (
            "time_sweep 60 1\n"
            "  continuous_measure_hall_field current=1e-3 nplc=5"
        ),
    },

    "measure_resistance": {
        "description": (
            "Sources a fixed DC current and measures resistance with the K2450. "
            "Either current= (A) or current_ma= (mA) is required."
        ),
        "positional": [],
        "kwargs": [
            _kw("current",       "float", "required",  "A",             "Source current (amps)"),
            _kw("current_ma",    "float", _NA,         "mA alias",      "Source current in mA (overrides current=)"),
            _kw("compliance",    "float", "10",        "V, > 0",        "Voltage compliance limit"),
            _kw("nplc",          "float", "1",         "0.001–10",      "Integration cycles"),
            _kw("voltage_range", "str",   "auto",      "V / mV / auto", "Fixed sense range"),
            _kw("settle_time",   "float", "0",         ">= 0 s",        "Delay after sourcing before measuring"),
            _kw("repetitions",   "int",   "1",         ">= 1",          "Number of readings to average"),
        ],
        "example": (
            "measure_resistance current=1e-3\n"
            "measure_resistance current_ma=0.5 voltage_range=20mV compliance=0.05\n"
            "measure_resistance current=1e-3 nplc=5 repetitions=3 settle_time=0.1"
        ),
    },

    "measure_iv_curve": {
        "description": (
            "Sweeps source current or voltage and records I-V data with the K2450. "
            "Use start + min + max + step for bidirectional sweeps. "
            "The shape= kwarg controls the sweep pattern."
        ),
        "positional": [],
        "kwargs": [
            _kw("mode",          "str",   "current",   "current / voltage",                  "Source mode"),
            _kw("shape",         "str",   "required",  "start_min_max_start / start_max_min_start\n"
                                                        "                               "
                                                        "start_min_start / start_max_start\n"
                                                        "                               "
                                                        "single (start→stop) / return (start→stop→start)", "Sweep pattern"),
            _kw("start",         "float", "required",  "A (current) / V (voltage)",           "First setpoint"),
            _kw("start_ma",      "float", _NA,         "mA alias for start",                  "start in mA"),
            _kw("min",           "float", _NA,         "A or V",                              "Minimum setpoint"),
            _kw("max",           "float", _NA,         "A or V",                              "Maximum setpoint"),
            _kw("min_ma",        "float", _NA,         "mA alias for min",                    ""),
            _kw("max_ma",        "float", _NA,         "mA alias for max",                    ""),
            _kw("stop",          "float", _NA,         "A or V (use min/max instead)",        "End setpoint (simple sweeps only)"),
            _kw("stop_ma",       "float", _NA,         "mA alias for stop",                   ""),
            _kw("step",          "float", "required",  "A or V, > 0",                         "Step size"),
            _kw("step_ma",       "float", _NA,         "mA alias for step",                   ""),
            _kw("compliance",    "float", "auto",      "V (current mode) / A (voltage mode)", "Compliance limit"),
            _kw("nplc",          "float", "1",         "0.001–10",                            "Integration cycles"),
            _kw("settle_time",   "float", "0",         ">= 0 s",                              "Delay at each setpoint"),
            _kw("repetitions",   "int",   "1",         ">= 1",                                "Readings averaged per point"),
            _kw("auto_range",    "bool",  "true",      "true/false",                          "Auto measurement range"),
            _kw("ramp_to_start", "bool",  "true",      "true/false",                          "Step source back to start after sweep"),
            _kw("keep_output",   "bool",  "false",     "true/false",                          "Leave source on after sweep"),
            _kw("source_range",  "float", "auto",      "A or V",                              "Fixed source range"),
            _kw("source_range_ma","float",_NA,         "mA alias for source_range",           ""),
            _kw("measure_range", "float", "auto",      "V (current mode) / A (voltage mode)", "Fixed measurement range"),
            _kw("measure_range_ma","float",_NA,        "mA alias for measure_range",          ""),
        ],
        "example": (
            "measure_iv_curve mode=current shape=start_min_max_start \\\n"
            "  start_ma=0 min_ma=-1 max_ma=1 step_ma=0.1 auto_range=true\n"
            "\n"
            "measure_iv_curve mode=current shape=single \\\n"
            "  start=0 stop=1e-3 step=1e-4 compliance=5 ramp_to_start=false"
        ),
    },

    "set_ppms_field_and_fix_hall": {
        "description": (
            "Sets the PPMS magnet to a target field and simultaneously adjusts the Helmholtz coil "
            "so that the Hall field stays at a fixed target value."
        ),
        "positional": [
            _pos("field_Oe",       "float", "Oe", "any", "PPMS magnet target field"),
            _pos("target_hall_G",  "float", "G",  "any", "Desired net Hall field to maintain"),
        ],
        "kwargs": [
            _kw("helmholtz_rate",     "float", "5.0",   "mA/s, > 0", "Helmholtz ramp rate"),
            _kw("max_current_change", "float", "2.0",   "A",         "Max Helmholtz current adjustment per step"),
        ],
        "example": (
            "set_ppms_field_and_fix_hall 5000 0.0\n"
            "set_ppms_field_and_fix_hall 5000 100.0 helmholtz_rate=10 max_current_change=1.5"
        ),
    },

    "scan_ppms_field_and_fix_hall": {
        "description": (
            "Steps the PPMS field and adjusts Helmholtz to keep Hall field fixed at each step. "
            "Runs its indented body at each setpoint."
        ),
        "positional": [
            _pos("start",         "float", "Oe", "any", "Start field"),
            _pos("end",           "float", "Oe", "any", "End field"),
            _pos("step",          "float", "Oe", "> 0", "Step size"),
            _pos("target_hall_G", "float", "G",  "any", "Hall field to maintain"),
        ],
        "kwargs": [
            _kw("rate",               "float", "10.0", "Oe/s, > 0", "PPMS field ramp rate"),
            _kw("helmholtz_rate",     "float", "5.0",  "mA/s, > 0", "Helmholtz ramp rate"),
            _kw("max_current_change", "float", "2.0",  "A",         "Max Helmholtz current change per step"),
        ],
        "example": (
            "scan_ppms_field_and_fix_hall 0 5000 500 0.0 rate=20\n"
            "  measure_lockin avg=15"
        ),
    },

    "full_measure": {
        "description": (
            "Performs a combined Hall + Lock-In measurement on the active channel. "
            "Sources the Hall current, reads Hall voltage, then reads Lock-In X/Y/R/θ."
        ),
        "positional": [],
        "kwargs": [
            _kw("time_between",         "float", "0",     ">= 0 s",     "Delay between Hall and Lock-In reads"),
            _kw("hall_current",         "float", "1e-3",  "A",          "Hall source current"),
            _kw("hall_nplc",            "float", "10",    "0.001–10",   "Hall integration cycles"),
            _kw("hall_compliance",      "float", "10",    "V, > 0",     "Hall voltage compliance"),
            _kw("hall_voltage_range",   "str",   "auto",  "V / auto",   "Hall sense range"),
            _kw("hall_filter",          "int",   "10",    "1–100",      "Hall filter depth"),
            _kw("hall_excitation",      "str",   "set",   "set / keep", "'keep' reuses existing K2450 source state"),
            _kw("tbm",                  "float", "0",     ">= 0 s",     "Time Before Measurement delay"),
            _kw("lockin_what",          "str",   "X,Y,R,Theta","csv of X/Y/R/Theta","Lock-In quantities to record"),
            _kw("lockin_current",       "float", "app",   "A",          "Lock-In excitation current"),
            _kw("lockin_series_resistance","float","app", "Ω",          "Series resistance for Lock-In"),
            _kw("lockin_avg",           "int",   "10",    ">= 1",       "Lock-In averages per reading"),
            _kw("lockin_start_sens",    "int",   "app",   "0–26",       "Initial Lock-In sensitivity index"),
            _kw("lockin_use_autorange", "bool",  "true",  "true/false", "Auto-range Lock-In sensitivity"),
            _kw("lockin_use_autophase", "bool",  "true",  "true/false", "Auto-phase Lock-In before reading"),
            _kw("lockin_sample_delay",  "float", "0.05",  ">= 0 s",     "Delay before reading Lock-In"),
        ],
        "example": (
            "full_measure\n"
            "full_measure hall_excitation=keep hall_nplc=10 lockin_avg=20\n"
            "full_measure time_between=0.1 hall_filter=20 lockin_use_autophase=false"
        ),
    },

    "continuous_full_measure": {
        "description": (
            "Like full_measure but intended for use inside time_sweep / for_loop. "
            "Keeps the Hall source enabled between measurements for speed."
        ),
        "positional": [],
        "kwargs": [
            _kw("time_between",         "float", "0",    ">= 0 s",   "Delay between Hall and Lock-In reads"),
            _kw("hall_nplc",            "float", "10",   "0.001–10", "Hall integration cycles"),
            _kw("hall_compliance",      "float", "10",   "V, > 0",   "Hall compliance"),
            _kw("hall_voltage_range",   "str",   "auto", "V / auto", "Hall sense range"),
            _kw("hall_filter",          "int",   "10",   "1–100",    "Hall filter depth"),
            _kw("lockin_what",          "str",   "X,Y,R,Theta","csv","Lock-In quantities"),
            _kw("lockin_avg",           "int",   "10",   ">= 1",     "Lock-In averages"),
            _kw("lockin_use_autorange", "bool",  "true", "true/false","Auto-range Lock-In"),
            _kw("lockin_use_autophase", "bool",  "true", "true/false","Auto-phase Lock-In"),
            _kw("lockin_sample_delay",  "float", "0.05", ">= 0 s",   "Delay before Lock-In read"),
        ],
        "example": (
            "time_sweep 120 1\n"
            "  continuous_full_measure hall_nplc=5 lockin_avg=15"
        ),
    },

    # ── Lock-In ─────────────────────────────────────────────────────────
    "measure_lockin": {
        "description": "Reads X, Y, R, and/or θ from the SR830 Lock-In amplifier and records one data point.",
        "positional": [],
        "kwargs": [
            _kw("what",             "str",   "X,Y,R,Theta","X / Y / R / Theta","Quantities to read (comma-separated)"),
            _kw("current",          "float", "app",      "A",                  "Lock-In output current (0 = off)"),
            _kw("series_resistance","float", "app",      "Ω",                  "Calibration series resistance"),
            _kw("avg",              "int",   "app",      ">= 1",               "Number of readings to average"),
            _kw("start_sens",       "int",   "app",      "0–26",               "Starting sensitivity index for autorange"),
            _kw("use_autorange",    "bool",  "true",     "true/false",          "Auto-range sensitivity before reading"),
            _kw("use_autophase",    "bool",  "true",     "true/false",          "Auto-phase before reading"),
            _kw("sample_delay",     "float", "0.05",     ">= 0 s",             "Delay before reading"),
        ],
        "example": (
            "measure_lockin\n"
            "measure_lockin avg=20 sample_delay=0.1\n"
            "measure_lockin what=X,Y use_autorange=false use_autophase=false"
        ),
    },

    "continuous_measure_lockin": {
        "description": "Like measure_lockin, intended for use inside time_sweep / for_loop. Faster: skips autorange/autophase.",
        "positional": [],
        "kwargs": [
            _kw("what",         "str",   "X,Y,R,Theta","csv","Quantities to read"),
            _kw("avg",          "int",   "app",    ">= 1", "Averages per reading"),
            _kw("sample_delay", "float", "0.05",   ">= 0 s","Delay before reading"),
        ],
        "example": (
            "time_sweep 60 1\n"
            "  continuous_measure_lockin avg=5 sample_delay=0.02"
        ),
    },

    "auto_gain": {
        "description": "Runs the SR830 auto-gain (auto-sensitivity) routine.",
        "positional": [],
        "kwargs": [],
        "example": "auto_gain",
    },

    "auto_phase": {
        "description": "Runs the SR830 auto-phase routine to minimise Y (maximise X).",
        "positional": [],
        "kwargs": [],
        "example": "auto_phase",
    },

    "auto_reserve": {
        "description": "Runs the SR830 auto-reserve routine.",
        "positional": [],
        "kwargs": [],
        "example": "auto_reserve",
    },

    "set_lockin_time_constant": {
        "description": "Sets the SR830 time constant (integration bandwidth).",
        "positional": [
            _pos("seconds", "float", "s", (
                "10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3,\n"
                "                     "
                "100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1000, 3000"
            ), "Time constant; nearest valid value is chosen"),
        ],
        "kwargs": [],
        "example": (
            "set_lockin_time_constant 0.3\n"
            "set_lockin_time_constant 1.0"
        ),
    },

    "set_lockin_sensitivity": {
        "description": "Sets the SR830 sensitivity (input range) by index.",
        "positional": [
            _pos("index", "int", "", (
                "0=2nV  1=5nV  2=10nV  3=20nV  4=50nV  5=100nV\n"
                "                     "
                "6=200nV  7=500nV  8=1µV  9=2µV  10=5µV  11=10µV\n"
                "                     "
                "12=20µV  13=50µV  14=100µV  15=200µV  16=500µV\n"
                "                     "
                "17=1mV  18=2mV  19=5mV  20=10mV  21=20mV  22=50mV\n"
                "                     "
                "23=100mV  24=200mV  25=500mV  26=1V"
            ), "Sensitivity index (0–26)"),
        ],
        "kwargs": [],
        "example": (
            "set_lockin_sensitivity 14    # 100 µV\n"
            "set_lockin_sensitivity 17    # 1 mV"
        ),
    },

    "set_lockin_filter": {
        "description": "Sets the SR830 low-pass filter roll-off slope.",
        "positional": [
            _pos("db_oct", "int", "dB/oct", "6, 12, 18, or 24", "Filter slope"),
        ],
        "kwargs": [],
        "example": (
            "set_lockin_filter 12\n"
            "set_lockin_filter 24"
        ),
    },

    "set_lockin_frequency": {
        "description": "Sets the SR830 internal oscillator reference frequency.",
        "positional": [
            _pos("freq_hz", "float", "Hz", "> 0", "Reference frequency"),
        ],
        "kwargs": [],
        "example": (
            "set_lockin_frequency 1234.5\n"
            "set_lockin_frequency 500.0"
        ),
    },

    "set_lockin_current": {
        "description": "Sets the SR830 output current (via voltage output ÷ series resistance). Setting 0 turns the output off.",
        "positional": [
            _pos("current_A", "float", "A", "any (0 = off)", "Desired output current"),
        ],
        "kwargs": [
            _kw("series_resistance", "float", "app", "Ω, > 0", "Calibration series resistance"),
        ],
        "example": (
            "set_lockin_current 3e-3\n"
            "set_lockin_current 5e-6 series_resistance=10000\n"
            "set_lockin_current 0    # turns output off"
        ),
    },

    # ── Switch ───────────────────────────────────────────────────────────
    "close_channel": {
        "description": "Routes the switch to a logical channel (a–j), closing all four required crosspoints.",
        "positional": [
            _pos("channel", "str", "", "a–j (based on switch capacity)", "Logical channel to route"),
        ],
        "kwargs": [],
        "example": (
            "close_channel a\n"
            "close_channel c"
        ),
    },

    "open_all_channels": {
        "description": "Opens (disconnects) all switch crosspoints.",
        "positional": [],
        "kwargs": [],
        "example": "open_all_channels",
    },

    "configure_channel": {
        "description": (
            "Assigns routing pin numbers (I+, V+, V−, I−) to a logical channel. "
            "Changes take effect immediately and persist for the session."
        ),
        "positional": [
            _pos("channel", "str", "",  "a–j",   "Logical channel name to configure"),
            _pos("I+",      "int", "",  "1–10",  "Pin number for current source (+)"),
            _pos("V+",      "int", "",  "1–10",  "Pin number for voltage sense (+)"),
            _pos("V-",      "int", "",  "1–10",  "Pin number for voltage sense (−)"),
            _pos("I-",      "int", "",  "1–10",  "Pin number for current return (−)"),
        ],
        "kwargs": [],
        "example": (
            "configure_channel a 5 6 7 8\n"
            "configure_channel b 1 2 3 4\n"
            "configure_channel c 9 10 7 8   # uses pins 9,10 (Keithley7001 only)"
        ),
    },
}
