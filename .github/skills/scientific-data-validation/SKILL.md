---
name: scientific-data-validation
description: "Use when adding or modifying measured and derived scientific values, calibration conversions, sanity checks, and non-physical value handling. Keywords: NaN, outlier, unit consistency, calibration, derived metric."
---

# Scientific Data Validation

## Workflow

1. Define expected physical ranges and units for each quantity.
2. Handle non-finite values and divide-by-zero explicitly.
3. Keep conversions explicit and centralized.
4. Validate consistency across channels when combining signals.
5. Flag suspicious results before downstream plotting or export.
6. Add numeric tests for nominal and edge scenarios.

## Validation

- At least one expected-value test for each new derived metric.
- Non-finite handling is deterministic.
- Calibration-dependent values are verified against calibration logic.

## Common Mistakes

- Implicit unit assumptions in formulas.
- Returning plausible numbers from invalid inputs.
- Missing checks for channel consistency.

## Project Anchors

- [Safe division helper](v3/core/measurements.py#L91)
- [Mock hall branch check](v3/core/measurements.py#L117)
- [Resistance measurement entry](v3/core/measurements.py#L646)
- [CalibrationConfig dataclass](v3/core/calibration.py#L14)
- [current_to_field conversion](v3/core/calibration.py#L60)
- [field_to_current conversion](v3/core/calibration.py#L64)
- [Calibration tests](v3/tests/test_calibration.py#L1)
- [Script numeric argument contracts](v3/core/script_parser.py#L209)
