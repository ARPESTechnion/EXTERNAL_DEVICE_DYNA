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

### 2.3 Switch backend selection

Switch backend is configured in `v3/core/constants.py`:

- `SWITCH_BACKEND = "my_switch"` (legacy behavior)
- `SWITCH_BACKEND = "keithley7001"` (new Keithley 7001 driver)

Address constants:

- `SWITCH_ADDRESS_MY` for the legacy switch
- `SWITCH_ADDRESS_7001` for Keithley 7001

The app keeps the same runtime workflow (`connect -> open_all -> measurement commands`) for both backends.

**GUI Features:**
- **Script editor:** Vertical and horizontal scrollbars for long command lines
- **Commands popup:** Categorized command browser with vertical and horizontal scrollbars, search, quick insert/copy
- **Save prompts:** When script has unsaved changes and you run/load, a 4-button dialog offers: Save, Save As, No, Cancel

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
  - LockIn settings include input shield mode toggle (Floating/Grounded), default Floating.
4. In Results tab:
   - **Quick instrument control via double-click popups:** Double-click any status readout in the Results tab to open a quick-control popup for that instrument:
     - **PPMS (Temperature)**: Set Temperature, Rate, Approach mode
     - **PPMS (Field)**: Set Field, Rate, Approach mode
     - **PPMS (Chamber)**: Set Chamber mode (Seal/Purge/Vent/etc.)
     - **Helmholtz**: Set Current/Field, Compliance, Ramp rates, Enable/Disable output
     - **Lock-In**: Frequency, Time Constant, Sensitivity, Filter, Output Current (with LED indicator), R_lockin selection, Input Shield toggle, Auto Gain/Phase/Reserve utilities
     - Sine Output LED: Green when reference amplitude exceeds idle threshold (0.004V + ε); synced with real-time output voltage from instrument
     - **Hall Bar**: Preset selection, Current, NPLC, Compliance, Filter, Offset, Hall measurement buttons
     - **Switch**: Channel configuration and open/close controls
   - Each popup is singleton (reused if already open), always-on-top, with close button in lower right corner
   - Choose/initialize data file
   - Optionally enable session header metadata (user/sample)
  - Write script in editor (or load saved script)
  - Use `Commands` helper popup (search, categorized fold/unfold list, insert/copy snippets)
  - Configure Graph 1 / Graph 2 independently (axes, style, color, and per-graph channel filters)
5. Run script and monitor status LEDs/logs/live values.
6. Abort/Pause/Resume as needed.
7. Review generated CSV in `Data_Route/` (or chosen directory).
8. In Switch tab (optional), export or load channel configurations between measurement sessions.

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
  - `measure_resistance`
  - `measure_iv_curve`
  - `enable_hall_output`
  - `disable_hall_output`
- LockIn measurement:
  - `measure_lockin`
  - `continuous_measure_lockin`
  - `full_measure` — combined open-all → close-channel(s) → measure-hall + measure-lockin → reopen-all
    - Supports `hall_excitation=cycle|keep` to control Hall current source:
      - `cycle` (default): measure Hall, then disable output (close current loop)
      - `keep`: measure Hall without managing excitation (keeps ongoing excitation)
  - `continuous_full_measure` — as `full_measure` but repeated until script/loop ends
- LockIn utilities:
  - `auto_gain`
  - `auto_phase`
  - `auto_reserve`
  - `set_lockin_time_constant`
  - `set_lockin_sensitivity`
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
  - `time_sweep`
  - `for_loop`

Command categories:
- Setpoints: `set_dyna_temp`, `set_dyna_field`, `set_helmholtz_field`
- Measurements: `measure_hall_field`, `continuous_measure_hall_field`, `measure_resistance`, `measure_iv_curve`, `measure_lockin`, `continuous_measure_lockin`, `full_measure`, `continuous_full_measure`
- Hall source control: `enable_hall_output`, `disable_hall_output`
- LockIn utilities: `auto_gain`, `auto_phase`, `auto_reserve`, `set_lockin_*`
- Wait/coordination: `wait_for ...`, `time_sweep ...`, `for_loop ...`
- Switch control: `open_all_channels`, `close_channel`, `configure_channel`
- File/script: `initialize_data_file`, `add_note`, `run_saved_script`
- Loop commands: `scan_*`, `sweep_*`, `time_sweep`, `for_loop` with indented child commands
- Loop nesting: maximum depth is 5 levels (deeper nesting is rejected by validation)

PPMS Hall-correction safety keywords:
- `set_ppms_field_and_fix_hall <field_Oe> <target_hall_G> [helmholtz_rate=0.1] [max_current_change=2.0]`
- `scan_ppms_field_and_fix_hall <start_Oe> <end_Oe> <step_Oe> <target_hall_G> [rate=10.0] [helmholtz_rate=0.1] [max_current_change=2.0]`
- `max_current_change` is in total Helmholtz current Amps and defaults to `2.0`.
- If a single Hall-fix step needs more than `max_current_change`, script execution fails fast with a command error.
- If the resulting Helmholtz target exceeds hardware safety current limits, script execution fails fast with a command error.

LockIn sensitivity utility:
- `set_lockin_sensitivity <index>` sets SR830 sensitivity directly.
- Valid `index` values are integers `0..26`.
- Command updates the LockIn GUI sensitivity selector and applies immediately to the instrument.

IV command updates (latest):
- `measure_iv_curve` supports preferred syntax `start + min + max + step` and fallback `start + stop + step`.
- Current-mode aliases are supported: `start_ma`, `min_ma`, `max_ma`, `stop_ma`, `step_ma`.
- Range kwargs are mode-aware:
  - `source_range`: current mode uses current range; voltage mode uses voltage range.
  - `measure_range`: current mode uses voltage sense range; voltage mode uses current sense range.
- Extra aliases are supported for current ranges:
  - `source_range_ma` (current mode)
  - `measure_range_ma` (voltage mode)
- Bounds validation is enforced: `min < start < max` and `min < max`.
- IV run logging reports point count, elapsed time, and engine mode (`fast` or `point` fallback).
- Cleanup/ramp status text is intentionally omitted from the Hall status log.

Example:

```txt
initialize_data_file filename=run1.csv append=false
set_dyna_temp 300 2 fast_settle
wait_for temp 3
measure_hall_field current=1 nplc=1 filter_count=5
close_channel c
for_loop 3
  measure_lockin avg=10
time_sweep 10 1
  continuous_measure_hall_field current=1 nplc=1
open_all_channels
```

Channel notes:
- switch commands (`close_channel`, `configure_channel`, `full_measure`) accept logical channels `a`..`h`
- Switch tab supports add/remove/clone/template workflows for faster multi-channel setup
- Switch tab can export/load channel mappings (`Export Configurations` / `Load Configurations`) for reuse

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
  - Supports both current-based (A) and field-based (Gauss) setpoints with automatic bidirectional conversion.
  - Two-channel resistance monitoring (Ch A, Ch B) with live Ω display alongside current readouts.
- `v3/gui/lockin_tab.py` — LockIn settings, auto-actions, single measurement actions.
  - Includes Input Shield mode control (Floating/Grounded) in Lock-In Settings.
- `v3/gui/results_tab.py` — results dashboard, script editor/runner controls, plotting/log panels.
  - **Script editor:** Syntax highlighting with Courier font, Ctrl+Z/Y undo/redo, Ctrl+A select all, Ctrl+S save, Ctrl+O load, Ctrl+Enter run
    - Includes vertical and horizontal scrollbars for editing long command lines
  - **Commands helper popup:** Categorized command browser (search, fold/unfold categories) with vertical and horizontal scrollbars
    - Quick insert/copy actions, double-click to insert into editor
  - **Quick-control popups:** Double-click any instrument status readout to open a focused control popup specific to that instrument. All 7 popup types (PPMS ×3, Helmholtz, LockIn, Hall, Switch) reuse existing tab handlers and maintain singleton lifecycle with always-on-top behavior.
  - **Live readouts with dual display:** Helmholtz status shows current (A) and resistance (Ω) combined on same line, matching tab layout. All PPMS, Helmholtz, Hall, and Lock-In readouts live-sync from instrument tabs.
  - **Lock-In popup output indicator:** Sine Output LED (green when active) that tracks real-time output voltage with same logic as main Lock-In tab LED.
  - Includes independent Graph 1/Graph 2 channel filters and 8-color graph palette.
- `v3/gui/script_runner.py` — command dispatcher + loop execution runtime used by worker engine.
- `v3/gui/switch_tab.py` — switch routing control and optional annotated wiring image tools.
  - Includes configuration management tools (add/remove/clone/templates + load/export mappings).

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
