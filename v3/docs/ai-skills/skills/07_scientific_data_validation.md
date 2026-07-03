# Skill 07: Scientific Data Validation

## Activate When

- Introducing new measured quantities, derived quantities, or channel combinations.
- Modifying conversion formulas, calibration usage, or result filtering.

## Mandatory Development Steps

1. Define physically valid ranges and expected sign/magnitude behavior.
2. Validate numeric integrity (`NaN`, `inf`, divide-by-zero, empty signals).
3. Keep unit conversions explicit and centralized.
4. Add sanity checks for channel consistency where applicable.
5. Mark suspicious data (or fail fast) before downstream analysis/export.
6. Add tests for nominal, edge, and non-physical input scenarios.

## Validation and Review Requirements

- At least one test per new derived metric with known expected value.
- Non-finite and zero-denominator behavior is explicitly handled.
- Calibration-dependent outputs validated against calibration tests.
- Reviewer confirms that suspicious values cannot silently pass as valid.

## Common Mistakes to Avoid

- Implicit unit assumptions in formulas.
- Swallowing invalid values and returning plausible-looking numbers.
- Missing consistency checks when combining channels or snapshots.
- Treating mock-perfect data as representative of real acquisition quality.

## In-Project Examples

- `v3/core/measurements.py`: `_safe_div`, `_avg_or_nan`, coercion helpers, derived fields.
- `v3/core/calibration.py` and `v3/tests/test_calibration.py`: conversion correctness.
- `v3/core/script_parser.py`: argument validation and typed extraction.

## Quick Mode (Token Lite)

- Units stated and conversion point explicit.
- Non-finite handling defined.
- One sanity bound check added.
- One numeric regression test added.
