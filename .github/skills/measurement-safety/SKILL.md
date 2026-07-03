---
name: measurement-safety
description: "Use when implementing source limits, compliance, ramping, startup/shutdown, and script commands that move field/current/temperature. Prevent unsafe operations for instruments and samples. Keywords: compliance, safety limit, ramp, shutdown, Helmholtz, Keithley."
---

# Measurement Safety

## Workflow

1. Validate requested setpoints against hard limits before applying.
2. Configure compliance before enabling outputs.
3. Use controlled ramps for transitions; avoid large abrupt changes.
4. Prime instrument mode or range when known firmware edge cases exist.
5. Ensure safe startup and fail-safe shutdown ordering.
6. Raise explicit safety errors and stop unsafe sequences immediately.

## Validation

- Unit tests cover out-of-range and compliance-trigger behavior.
- Abort and disconnect paths leave hardware in safe state.
- Parser or input validation blocks unsafe arguments.

## Common Mistakes

- Enabling outputs before setting compliance and range.
- Assuming previous instrument state is safe.
- Forgetting to disable outputs on exception exits.

## Project Anchors

- [Hard current safety limit](v3/core/constants.py#L61)
- [ComplianceError definition](v3/core/helmholtz_controller.py#L77)
- [HelmholtzSafetyError definition](v3/core/helmholtz_controller.py#L81)
- [Helmholtz set_field safety gate](v3/core/helmholtz_controller.py#L191)
- [Helmholtz disable_output safe shutdown](v3/core/helmholtz_controller.py#L280)
- [Resistance measurement compliance logic](v3/core/measurements.py#L646)
- K2450 5077 precondition memory: /memories/repo/k2450-resistance-autorange-5077-safe-precondition.md line 1
