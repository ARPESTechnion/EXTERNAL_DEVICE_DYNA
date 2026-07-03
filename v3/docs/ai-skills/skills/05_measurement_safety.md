# Skill 05: Measurement Safety and Hardware Protection

## Activate When

- Changing source settings, compliance limits, ramping logic, or measurement sequencing.
- Adding new script commands that can move field/current/temperature.

## Mandatory Development Steps

1. Validate requested setpoints against hard safety constants before applying.
2. Apply compliance limits explicitly before enabling outputs.
3. Use controlled ramping for transitions; avoid abrupt large jumps.
4. Prime instrument modes/ranges where known firmware edge cases exist.
5. Enforce safe startup and shutdown order (enable only after setup, disable on exit/errors).
6. Propagate safety exceptions clearly and stop unsafe sequences immediately.

## Validation and Review Requirements

- Unit tests cover out-of-range and compliance-trigger scenarios.
- Safe behavior verified for abort/stop and disconnect paths.
- Script parser validation rejects unsafe or malformed arguments.
- Logs include enough context to diagnose near-miss safety events.

## Common Mistakes to Avoid

- Setting output before configuring compliance and mode.
- Assuming prior instrument state is safe or unchanged.
- Forgetting to clamp user-entered limits to physical constraints.
- Leaving outputs enabled after exceptions.

## In-Project Examples

- `v3/core/constants.py`: hard limits (`HELMHOLTZ_MAX_CURRENT_A`, range bounds).
- `v3/core/helmholtz_controller.py`: `ComplianceError`, `HelmholtzSafetyError`, ramp/service logic.
- `v3/core/measurements.py`: compliance clamping and range preconditioning.
- `/memories/repo/k2450-resistance-autorange-5077-safe-precondition.md`: known unsafe state mitigation.

## Quick Mode (Token Lite)

- Limits checked before set.
- Compliance configured first.
- Ramping used for transitions.
- Exception path disables output safely.
