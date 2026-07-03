# Skill 10: Code Review Process for Measurement Reliability

## Activate When

- Final review for any task before merge/completion.

## Mandatory Development Steps

1. Review for functional correctness and edge cases first.
2. Review communication reliability (timeouts, retries, stale-buffer risk).
3. Review safety-critical behavior (limits, compliance, shutdown on error).
4. Review thread safety (UI thread vs worker thread boundaries).
5. Review data integrity (schema, units, metadata, export consistency).
6. Review maintainability (clarity, duplication, constants usage, test quality).

## Validation and Review Requirements

- Findings are listed by severity with concrete file anchors.
- High-severity issues are resolved or explicitly accepted with rationale.
- Required tests run for affected subsystem.
- Residual risk and untested areas are documented.

## Common Mistakes to Avoid

- Focusing on style while missing safety/protocol regressions.
- Approving behavior changes without tests.
- Ignoring thread-boundary violations in GUI code.
- Skipping schema checks when data fields change.

## In-Project Examples

- `v3/tests/test_instrument_bus.py`: deadlock/race prevention checks.
- `v3/tests/test_helmholtz_controller.py`: ramp/safety behavior checks.
- `v3/tests/test_measurements.py`: logic and integration edge cases with mocks.
- `/memories/repo/k2450-resistance-autorange-5077-safe-precondition.md`: example of hidden hardware-state regression.

## Quick Mode (Token Lite)

- Severity-ordered findings captured.
- Safety/protocol/threading/data checks done.
- Relevant tests run.
- Residual risks noted.
