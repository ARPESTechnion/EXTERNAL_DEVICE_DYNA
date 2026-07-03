# v3 AI Skill Pack

This folder contains a reusable AI-assisted development skill set derived from the active `v3` codebase and its supporting drivers in `Utility`.

## Deliverables in This Pack

1. `PATTERN_AUDIT_SUMMARY.md` - concise summary of discovered engineering patterns.
2. `skills/01_instrument_communication_manual_first.md`
3. `skills/02_driver_architecture.md`
4. `skills/03_mock_first_development.md`
5. `skills/04_gui_design_system_laboratory.md`
6. `skills/05_measurement_safety.md`
7. `skills/06_data_logging_standards.md`
8. `skills/07_scientific_data_validation.md`
9. `skills/08_plotting_standards.md`
10. `skills/09_refactoring_guidelines.md`
11. `skills/10_code_review_process.md`

## Always-On Skills (recommended baseline)

- 01 Instrument Communication and Manual-First Command Design
- 02 Driver Architecture Consistency
- 05 Measurement Safety
- 06 Data Logging Standards
- 10 Code Review Process

## Task-Specific Skills

- 03 Mock-First Development: activate for tests, offline development, or hardware unavailability.
- 04 GUI Design System for Laboratory Workflows: activate for any Tkinter/UI change.
- 07 Scientific Data Validation: activate when adding or modifying measured quantities or derived metrics.
- 08 Plotting Standards: activate when creating or changing plots and exports.
- 09 Refactoring Guidelines: activate for structural changes, API cleanup, or deduplication.

## Token-Efficient Usage Strategy

Use two execution levels:

- Quick mode: run only each skill's Quick Mode checklist and examples.
- Deep mode: run all Mandatory Steps and Validation sections.

Use trigger words to activate only relevant skills:

- "SCPI", "VISA", "GPIB", "driver" -> 01, 02, 05, 10
- "mock", "test", "offline" -> 03, 10
- "tab", "widget", "Tk", "status" -> 04, 10
- "CSV", "metadata", "schema", "log" -> 06, 07, 10
- "plot", "axis", "legend", "export" -> 08, 10
- "refactor", "cleanup", "rename", "compat" -> 09, 10
