# Pattern Audit Summary (v3)

Scope: active `v3` tree is authoritative, with supporting evidence from `Utility` drivers and project bug-history memories.

## 1) Instrument Communication and Manual Usage

Observed patterns:

- Explicit low-level command wrappers (`write`, `query`) and startup ID checks in `Utility/Keithley2450.py` and `Utility/New_LockIn.py`.
- SR830-specific stale-buffer mitigation in `Utility/New_LockIn.py` using `_clear_buffer()` and retry backoff.
- Timeouts and recovery behavior reinforced by project memories (`/memories/repo/sr830-auto-wait.md`, `/memories/repo/k2450-query-interrupted-trace-reply-contamination.md`).

## 2) Driver Architecture

Observed patterns:

- Centralized access via `v3/core/instrument_bus.py` with per-instrument locking and deadlock guard.
- Measurement logic separated from UI in `v3/core/measurements.py` (pure functions with `MeasurementContext`).
- Canonical names and limits in `v3/core/constants.py`.

## 3) Mock-First Development

Observed patterns:

- Mock drivers with realistic behavior and noise (`Utility/Mock_Kethley2450.py`).
- Explicit mock marker (`is_mock_hall`) consumed in `v3/core/measurements.py`.
- Context-level mocking in tests (`v3/tests/test_measurements.py`, `v3/tests/test_script_runner.py`).

## 4) GUI Design System

Observed patterns:

- Shared theme tokens in `v3/gui/theme.py` (colors, fonts, spacing).
- Reusable tab foundations in `v3/gui/base_tab.py` and component set in `v3/gui/components`.
- Laboratory workflow emphasis in `v3/gui/results_tab.py`, `v3/gui/hall_tab.py`, `v3/gui/lockin_tab.py`, `v3/gui/helmholtz_tab.py`.

## 5) Measurement Safety

Observed patterns:

- Hard limits centralized in `v3/core/constants.py`.
- Safety exceptions and compliance/ramp control in `v3/core/helmholtz_controller.py`.
- Range preconditioning and compliance clamping in `v3/core/measurements.py` (aligned with `/memories/repo/k2450-resistance-autorange-5077-safe-precondition.md`).

## 6) Data Logging Standards

Observed patterns:

- Structured schema and key mapping via `CSV_FIELDNAMES` and `DATA_KEY_TO_CSV` in `v3/core/constants.py`.
- Header validation, append/new file handling, and auto-log rotation in `v3/core/data_manager.py`.

## 7) Scientific Data Validation

Observed patterns:

- Defensive helpers (`_safe_div`, `_avg_or_nan`, numeric coercion) in `v3/core/measurements.py`.
- Type/range parsing in `v3/core/script_parser.py`.
- Tests with numeric expectations and edge cases (`v3/tests/test_calibration.py`, `v3/tests/test_measurements.py`).

## 8) Plotting Standards

Observed patterns:

- Embedded Matplotlib with graceful fallback in `v3/gui/results_tab.py`, `v3/gui/dyna_tab.py`, `v3/gui/helmholtz_tab.py`.
- Explicit axis labels, legends, grid style, autoscale controls, and export paths in `v3/gui/results_tab.py`.

## 9) Refactoring Safety

Observed patterns:

- Backward compatibility handled via aliases and dual-parameter support in multiple v3 modules.
- Strict parser signatures in `v3/core/script_parser.py` guard against silent behavior drift.
- Regression tests target previously fragile areas (`v3/tests/test_instrument_bus.py`, `v3/tests/test_helmholtz_controller.py`).

## 10) Code Review Process

Observed patterns:

- Risk hotspots are communication reliability, thread safety, measurement safety, and schema stability.
- Existing tests are organized by subsystem and include mock-heavy unit tests in `v3/tests`.

## Recommended Activation Policy

Always on: 01, 02, 05, 06, 10.

Task specific: 03 (mock/testing), 04 (GUI), 07 (scientific validity), 08 (plotting), 09 (refactoring).

## Token Usage Guidance

- Start with always-on quick checklists.
- Activate only relevant task-specific skills using trigger words.
- Escalate to deep mode only when touching safety-critical paths, instrument protocol logic, or shared schemas.
