# Skill 03: Mock-First Development

## Activate When

- Implementing new measurement features without guaranteed hardware availability.
- Writing tests for instrument-dependent logic.
- Reproducing failure scenarios safely.

## Mandatory Development Steps

1. Implement or extend a mock with the same public API as the real driver.
2. Add realistic behavior: noise, delays, range effects, and deterministic options when needed.
3. Mark mock identity explicitly (for example `is_mock_hall`) when behavior diverges.
4. Inject dependencies through `MeasurementContext` or equivalent context objects.
5. Add unit tests using mocks for nominal flow and selected failure cases.

## Validation and Review Requirements

- Mock and real driver method signatures remain compatible.
- Tests run fully without physical hardware.
- At least one test validates behavior under non-ideal conditions (noise, timeout, invalid input).
- Mock-specific branches are explicit and minimal.

## Common Mistakes to Avoid

- Over-simplified mocks that always return ideal values.
- Drift between mock API and real driver API.
- Hidden mock behavior not declared by explicit flags.
- Tests that incidentally depend on connected hardware.

## In-Project Examples

- `Utility/Mock_Kethley2450.py`: simulated source/measure behavior, noise, and timing.
- `v3/core/measurements.py`: `_is_mock_hall_driver` branch pattern.
- `v3/tests/test_measurements.py`: context-level mock injection and verification.
- `v3/tests/test_script_runner.py`: patched dispatch and behavior tests.

## Quick Mode (Token Lite)

- API-compatible mock exists.
- Mock identity flag present if needed.
- One realistic non-ideal scenario included.
- Hardware-free tests pass.
