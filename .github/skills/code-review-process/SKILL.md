---
name: code-review-process
description: "Use as the final quality-control checklist before completing tasks. Focuses on bug and regression detection in instrument communication, safety, threading, data integrity, and maintainability. Keywords: review checklist, regression, edge cases, reliability."
---

# Code Review Process

## Workflow

1. Check functional correctness and edge-case behavior first.
2. Check communication reliability: timeout, retry, stale-response risks.
3. Check safety-critical behavior: compliance, limits, fail-safe shutdown.
4. Check thread boundaries between worker logic and GUI state.
5. Check data integrity: schema, units, metadata, exports.
6. Check maintainability: duplication, naming, constants reuse, test quality.

## Validation

- Findings are ordered by severity with concrete file anchors.
- High-severity findings are fixed or explicitly accepted.
- Relevant subsystem tests are run.
- Residual risk and untested scope are documented.

## Common Mistakes

- Approving style-clean code with hidden protocol regressions.
- Skipping tests after behavior changes.
- Missing GUI thread-safety violations.

## Project Anchors

- [InstrumentBus deadlock expectation](v3/tests/test_instrument_bus.py#L190)
- [InstrumentBus concurrent serialization test](v3/tests/test_instrument_bus.py#L234)
- [Helmholtz convergence test](v3/tests/test_helmholtz_controller.py#L125)
- [Measurements baseline test](v3/tests/test_measurements.py#L195)
- [Resistance measurement test](v3/tests/test_measurements.py#L266)
- K2450 5077 regression memory: /memories/repo/k2450-resistance-autorange-5077-safe-precondition.md line 1
