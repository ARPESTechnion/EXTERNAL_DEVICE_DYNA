# v3 Measurement System README

This README explains how to run and use the `v3` program, how the internal logic flows, and what each file does.

---

## 1) What this program is

`v3` is a Tkinter-based lab measurement application that coordinates:
- PPMS/Dyna temperature and magnetic field control
- Helmholtz coil control (Keithley 2600)
- Hall-bar voltage/field measurements (Keithley 2450)
- Lock-in measurements (SR830)
- Switch matrix channel routing
- Scripted measurement automation with loops and waits
- CSV data logging + auto-logging

It supports both **mock mode** (no hardware) and **real mode** (real instruments).

---

## 2) Quick start

### 2.1 Prerequisites

- Python 3.10+ (project currently validated in your environment with Conda)
- Required packages used by `v3`:
  - `numpy`
  - `pytest` (for tests)
- GUI/runtime optional-but-recommended packages depending on your usage:
  - `matplotlib` (plotting in GUI tabs)
  - `Pillow` (switch image/annotation tooling)
- For real instruments, the corresponding instrument libraries/drivers in `Utility/` must be available and working.

### 2.2 Run the app

From repository root:

```bash
python v3/run_app.py --mockup
```

or:

```bash
python v3/run_app.py --real
```

You can also edit `Use_MockUp` in `v3/run_app.py`.

### 2.3 Run tests

Run full v3 suite:

```bash
pytest -q v3/tests
```

Run a focused suite (example):

```bash
pytest -q v3/tests/test_script_runner.py v3/tests/test_measurements.py
```

---

## 3) User workflow (operator view)

1. Launch app in mock/real mode.
2. Connect required instruments using tab headers.
3. Configure tab parameters (Dyna, Helmholtz, LockIn, Hall, Switch).
4. In Results tab:
   - Choose/initialize data file
   - Optionally enable session header metadata (user/sample)
   - Write script in editor (or load saved script)
5. Run script and monitor status LEDs/logs/live values.
6. Abort/Pause/Resume as needed.
7. Review generated CSV in `Data_Route/` (or chosen directory).

---

## 4) Program logic and flow (detailed)

## 4.1 Startup and object wiring

- Entry point: `v3/run_app.py`
- App bootstrap: `v3/gui/app.py` (`main()` + `MeasureApp`)
- `MeasureApp` creates and wires core services:
  - `InstrumentBus`
  - `UIEventBus`
  - `DataManager`
  - `HelmholtzController`
  - `ExperimentEngine`
  - `ScriptParser` + `ScriptValidator`

It also creates all GUI tabs and starts periodic UI update + Dyna polling loops.

## 4.2 Script execution path

1. User presses Run Script in Results tab.
2. `MeasureApp.run_script()` parses script text (`ScriptParser`) and validates (`ScriptValidator`).
3. If valid, `ExperimentEngine.start()` launches worker thread.
4. Worker executes `v3/gui/script_runner.py::run_commands()`.
5. Each command dispatches to:
   - measurement/control functions in `v3/core/measurements.py`
   - or helper utilities in `script_runner.py`
6. Results are written through `DataManager.write_row()`.
7. UI status/live values are posted through `UIEventBus`.
8. Main Tk thread drains events and updates widgets.

### Fail-fast behavior

Command failures are logged and propagated (fail-fast), so script execution stops on command errors unless explicitly handled by logic.

### Nested scripts

`run_saved_script` supports nested includes with guardrails:
- relative path resolution from including script directory
- validation of nested script before execution
- recursion cycle detection
- max nesting depth limit

## 4.3 Measurement function pattern

Core measurement functions are in `v3/core/measurements.py` and are designed as pure logic around `MeasurementContext`:
- pull current context snapshots (temp/field/helmholtz)
- issue instrument bus calls
- compute derived values
- return a data-point dict

They do not directly manage GUI widgets.

### Mock Hall result model (mock mode)

In mock mode, Hall results are generated with a more realistic synthetic model (used only with the mock Hall driver):
- linear Helmholtz contribution
- small PPMS cross-axis contribution (default ~1%)
- configurable Hall offset
- noise composed of floor + relative terms

Conceptually:

`Hall_V ≈ (a*B_helmholtz + b*B_ppms + offset + noise) / V2Gauss`

The model parameters are configured in `v3/core/calibration.py` via `CalibrationConfig` (`hall_mock_*` fields), including an optional RNG seed for deterministic tests.

## 4.4 UI event architecture

Background workers/pollers never directly manipulate Tk widgets.
They post logical events to `UIEventBus` (`W_*` event IDs).
Main thread in `MeasureApp.update_ui()` drains and dispatches events to tabs.

This keeps cross-thread UI access safe and predictable.

## 4.5 Data and logging lifecycle

`DataManager` handles:
- data file initialization
- write-row mapping internal keys -> CSV columns
- append mode and time offset handling
- in-memory bounded results buffer for plotting
- optional session metadata header rows
- auto-log file management and rotation

### Normalized channel-aware schema

Current CSV rows use a normalized channel model:
- `Channel` stores the logical channel label (`a`..`h`) for that row
- lock-in values are stored in generic fields (`LockIn_X(V)`, `LockIn_Y(V)`, `LockIn_R(V)`, `LockIn_Theta(deg)` and corresponding `*_Error` columns)
- resistance is stored in `Sample_Resistance(Ohm)` (+ error column)

This replaces legacy duplicated per-channel lock-in columns and keeps each row self-describing.
In Results, this aligns with channel filtering/overlay plotting by logical channel.

### Append mode edge handling

When `append=true`:
- valid existing file: append continues and writes append note marker
- empty existing file: schema header is written first
- incompatible existing header: fallback to numbered new file for safety

## 4.6 Stop/abort safety path

On stop/abort request:
- `ExperimentEngine` signals stop and unwinds worker via `StopRequested`
- app abort cleanup attempts best-effort safe-state actions, including:
  - disabling Hall output
  - disabling/minimizing LockIn output
  - opening switch channels
  - ramping Helmholtz to zero (not force-disable)

---

## 5) DSL scripting model (quick reference)

Use full syntax/details in `Commands.txt`. This section is intentionally concise.

### 5.1 Complete command index (all commands)

The list below mirrors the parser command set in `v3/core/script_parser.py` (`VALID_COMMANDS` + loop commands).

- Basic:
  - `test`
- Data/file/script:
  - `initialize_data_file`
  - `add_note`
  - `run_saved_script`
- Dyna / PPMS set + correction:
  - `set_dyna_field`
  - `set_dyna_temp`
  - `set_ppms_field_and_fix_hall`
  - `scan_ppms_field_and_fix_hall`
- Helmholtz:
  - `set_helmholtz_field`
  - `scan_helmholtz_field`
  - `sweep_helmholtz_field`
- Waits:
  - `wait_for`
- Hall:
  - `measure_hall_field`
  - `continuous_measure_hall_field`
  - `enable_hall_output`
  - `disable_hall_output`
- LockIn measurement:
  - `measure_lockin`
  - `continuous_measure_lockin`
  - `full_measure`
- LockIn utilities:
  - `auto_gain`
  - `auto_phase`
  - `auto_reserve`
  - `set_lockin_time_constant`
  - `set_lockin_filter`
  - `set_lockin_frequency`
  - `set_lockin_current`
- Switch matrix:
  - `open_all_channels`
  - `close_channel`
  - `configure_channel`
- Loop commands (indented body):
  - `scan_dyna_field`
  - `scan_dyna_temp`
  - `sweep_dyna_field`
  - `sweep_dyna_temp`
  - `scan_helmholtz_field`
  - `sweep_helmholtz_field`

Command categories:
- Setpoints: `set_dyna_temp`, `set_dyna_field`, `set_helmholtz_field`
- Measurements: `measure_hall_field`, `continuous_measure_hall_field`, `measure_lockin`, `continuous_measure_lockin`, `full_measure`
- Hall source control: `enable_hall_output`, `disable_hall_output`
- LockIn utilities: `auto_gain`, `auto_phase`, `auto_reserve`, `set_lockin_*`
- Wait/coordination: `wait_for ...`
- Switch control: `open_all_channels`, `close_channel`, `configure_channel`
- File/script: `initialize_data_file`, `add_note`, `run_saved_script`
- Loop commands: `scan_*`, `sweep_*` with indented child commands
- Loop nesting: maximum depth is 5 levels (deeper nesting is rejected by validation)

Example:

```txt
initialize_data_file filename=run1.csv append=false
set_dyna_temp 300 2 fast_settle
wait_for temp 3
measure_hall_field current=1 nplc=1 filter_count=5
close_channel c
measure_lockin avg=10
open_all_channels
```

Channel notes:
- switch commands (`close_channel`, `configure_channel`, `full_measure`) accept logical channels `a`..`h`
- Switch tab supports add/remove/clone/template workflows for faster multi-channel setup

---

## 6) File-by-file role map

## 6.1 Top-level `v3/`

- `v3/__init__.py` — package marker.
- `v3/run_app.py` — application launcher and mode selection (`--mockup` / `--real`).

## 6.2 `v3/core/`

- `v3/core/__init__.py` — core package marker.
- `v3/core/calibration.py` — Hall/Helmholtz conversion math and calibration config.
- `v3/core/constants.py` — shared constants: addresses, CSV schema, UI timing, limits.
- `v3/core/data_manager.py` — CSV lifecycle, row writes, results buffer, auto-log management.
- `v3/core/experiment_engine.py` — worker-thread execution state machine (idle/running/paused/stopping/error).
- `v3/core/helmholtz_controller.py` — Helmholtz ramp logic, safety/compliance handling, live snapshot state.
- `v3/core/instrument_bus.py` — thread-safe instrument registry + method dispatch abstraction.
- `v3/core/measurements.py` — all measurement/control logic and wait primitives.
- `v3/core/script_parser.py` — DSL parser + validator (syntax, command args, instrument requirements).
- `v3/core/ui_events.py` — thread-safe UI event queue and widget event identifiers.

## 6.3 `v3/gui/`

- `v3/gui/__init__.py` — gui package marker.
- `v3/gui/app.py` — main Tk app orchestration, tab wiring, polling, shutdown, script start/abort.
- `v3/gui/base_tab.py` — shared tab base classes/utilities (headers/LED helpers).
- `v3/gui/dyna_tab.py` — Dyna controls and status display.
- `v3/gui/hall_tab.py` — Hall measurement UI and Hall-source settings.
- `v3/gui/helmholtz_tab.py` — Helmholtz setpoint/output controls and readouts.
- `v3/gui/lockin_tab.py` — LockIn settings, auto-actions, single measurement actions.
- `v3/gui/results_tab.py` — results dashboard, script editor/runner controls, plotting/log panels.
- `v3/gui/script_runner.py` — command dispatcher + loop execution runtime used by worker engine.
- `v3/gui/switch_tab.py` — switch routing control and optional annotated wiring image tools.

## 6.4 `v3/tests/`

- `v3/tests/__init__.py` — tests package marker.
- `v3/tests/command_smoke_script.txt` — DSL smoke script sample.
- `v3/tests/test_auto_logging_behavior.py` — auto-log behavior/rotation tests.
- `v3/tests/test_calibration.py` — calibration math tests.
- `v3/tests/test_data_manager.py` — CSV/append/results/auto-log tests.
- `v3/tests/test_experiment_engine.py` — engine state and stop/pause behavior tests.
- `v3/tests/test_gui.py` — GUI tab/update behavior tests.
- `v3/tests/test_helmholtz_controller.py` — Helmholtz ramp/controller tests.
- `v3/tests/test_instrument_bus.py` — bus threading/disconnect/dispatch tests.
- `v3/tests/test_measurements.py` — measurement logic and utility tests.
- `v3/tests/test_script_parser.py` — parser/validator correctness tests.
- `v3/tests/test_script_runner.py` — dispatch/loop/nested-script runtime tests.
- `v3/tests/test_ui_events.py` — UI event queue semantics tests.

---

## 7) Real mode notes (basic)

In real mode, verify:
- addresses and host/port in `v3/core/constants.py`
- physical instrument availability and permissions
- underlying instrument wrappers in `Utility/` can connect

If an instrument disconnects during script run, script execution requests stop for safety.

---

## 8) Troubleshooting

- **Script won’t start**: check validation errors in log pane; fix line/argument names.
- **No data file written**: ensure measurements executed; empty sessions are intentionally cleaned up.
- **Append didn’t use original file**: existing file may have incompatible header; numbered variant is used for safety.
- **GUI tests fail on headless environment**: some GUI tests require display/Tk context.
- **Instrument command errors**: check connection state, addresses, and whether command requires connected instrument.

---

## 9) Where to find deeper command docs

- Full script command reference: `Commands.txt`
- This README keeps command syntax concise by design.

---

## 10) Legacy docs note

Repository contains additional historical/patch notes (`*_FIXES.md`, `THREADING_ANALYSIS.md`, etc.).
Use this README + `Commands.txt` as current v3 operational references.
