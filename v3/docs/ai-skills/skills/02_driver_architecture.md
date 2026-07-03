# Skill 02: Driver Architecture Consistency

## Activate When

- Creating a new instrument driver or refactoring an existing one.
- Adding new measurement APIs that touch driver interfaces.

## Mandatory Development Steps

1. Keep low-level transport commands inside driver classes only.
2. Expose stable, intention-revealing public APIs (for example `apply_current`, `measure_voltage`).
3. Route operational calls through `InstrumentBus` for thread safety.
4. Keep measurement workflows in `v3/core/measurements.py` style pure functions, not GUI classes.
5. Place limits/defaults in `v3/core/constants.py`; avoid magic numbers.
6. Align naming with existing canonical instrument keys.
7. Add/update tests for new driver behavior and failure handling.

## Validation and Review Requirements

- No direct instrument method calls from GUI thread paths where bus access is required.
- Public method names and parameter units are consistent with existing drivers.
- New constants are centralized and referenced by name.
- Regression tests cover at least one happy path and one error path.

## Common Mistakes to Avoid

- Embedding UI logic in drivers.
- Coupling measurement calculations to transport details.
- Bypassing `InstrumentBus` and reintroducing race conditions.
- Introducing new unit conventions without migration guard.

## In-Project Examples

- `v3/core/instrument_bus.py`: per-instrument locking, deadlock guard, atomic execution.
- `v3/core/measurements.py`: context-injected pure logic functions.
- `v3/core/constants.py`: canonical addresses, limits, and schema constants.
- `v3/tests/test_instrument_bus.py`: thread-safety and deadlock guard tests.

## Quick Mode (Token Lite)

- Transport in driver only.
- Bus-mediated access only.
- Constants centralized.
- Pure measurement logic kept outside GUI.
- One unit test added for API contract.
