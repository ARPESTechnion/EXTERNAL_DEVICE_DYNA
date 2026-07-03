---
name: mock-first-development
description: "Use when implementing instrument-dependent features without guaranteed hardware access, or when writing tests for measurement workflows. Covers API-compatible mocks, failure simulation, and hardware-independent validation. Keywords: mock instrument, offline testing, MagicMock, simulation."
---

# Mock-First Development

## Workflow

1. Provide a mock with API parity to the real driver.
2. Simulate realistic behavior: noise, delay, range limits, and selected failure modes.
3. Mark mock identity clearly when branch behavior is needed.
4. Inject mocks through context objects (not hidden globals).
5. Add tests for nominal flow and at least one non-ideal scenario.

## Validation

- Tests run without physical hardware.
- Mock and real signatures remain aligned.
- Non-ideal behavior is exercised in tests.
- Mock-specific branching is explicit and minimal.

## Common Mistakes

- Idealized mocks that hide real-world edge cases.
- API drift between mock and real drivers.
- Hardware assumptions leaking into unit tests.

## Project Anchors

- [MockKeithley2450 class](Utility/Mock_Kethley2450.py#L4)
- [Mock driver identity flag](Utility/Mock_Kethley2450.py#L9)
- [Mock branch detector](v3/core/measurements.py#L117)
- [Measurement test baseline](v3/tests/test_measurements.py#L195)
- [Script runner mock dispatch test](v3/tests/test_script_runner.py#L167)
