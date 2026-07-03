---
name: driver-architecture-consistency
description: "Use when creating or refactoring instrument drivers and measurement APIs to preserve architecture consistency: bus-mediated access, clear driver boundaries, stable public API names, and separation of transport from measurement logic. Keywords: driver architecture, InstrumentBus, API consistency, refactor driver."
---

# Driver Architecture Consistency

## Workflow

1. Keep low-level communication inside driver classes only.
2. Keep measurement logic in v3/core measurement modules, not GUI tabs.
3. Route instrument operations through InstrumentBus for concurrency safety.
4. Place addresses, limits, and defaults in v3/core/constants.py.
5. Keep API names and units consistent with existing driver conventions.
6. Add regression tests for behavior and errors when APIs evolve.

## Validation

- No direct instrument transport calls from GUI logic.
- New constants are centralized and reused.
- API contracts are backward-compatible or explicitly migrated.
- Tests cover nominal path and one failure path.

## Common Mistakes

- Bypassing InstrumentBus locking.
- Mixing UI state and transport logic.
- Introducing magic numbers in new driver code.
- Changing method semantics without compatibility checks.

## Project Anchors

- [InstrumentBus class](v3/core/instrument_bus.py#L46)
- [InstrumentBus execute path](v3/core/instrument_bus.py#L116)
- [InstrumentBus acquire path](v3/core/instrument_bus.py#L172)
- [Measurement context-driven logic](v3/core/measurements.py#L52)
- [Canonical constants root](v3/core/constants.py#L1)
- [Deadlock guard test expectation](v3/tests/test_instrument_bus.py#L190)
