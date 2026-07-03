# Skill 09: Refactoring Guidelines for Scientific Control Software

## Activate When

- Reorganizing core modules, deduplicating logic, renaming APIs, or changing control flow.

## Mandatory Development Steps

1. Preserve public API contracts unless an explicit migration plan is included.
2. Isolate structural refactor from behavior change where possible.
3. Keep safety checks and communication ordering semantically identical unless intentionally changed.
4. Centralize duplicated constants/helpers instead of copying logic.
5. Add compatibility shims for renamed keys/parameters when existing scripts depend on them.
6. Expand tests around touched behavior before or during refactor.

## Validation and Review Requirements

- Existing scripts and core workflows still run without regression.
- Backward-compatible aliases or migration notes exist for breaking changes.
- No safety or instrument sequencing guarantees were dropped.
- Tests cover high-risk areas touched by refactor.

## Common Mistakes to Avoid

- Mixing cleanup and feature changes in one unreviewable patch.
- Removing aliases without checking script compatibility.
- Reordering instrument commands without understanding side effects.
- Refactoring tests away from realistic behavior.

## In-Project Examples

- `v3/core/script_parser.py`: strict signatures and validation protect script compatibility.
- `v3/core/measurements.py`: compatibility-conscious parameter handling and range logic.
- `v3/tests/test_script_parser.py` and `v3/tests/test_script_runner.py`: behavior lock tests.

## Quick Mode (Token Lite)

- Contract-preserving change boundary clear.
- Safety/ordering unchanged or explicitly reviewed.
- Compatibility path documented.
- Regression tests updated.
