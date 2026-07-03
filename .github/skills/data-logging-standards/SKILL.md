---
name: data-logging-standards
description: "Use when changing CSV schema, metadata rows, append behavior, auto-log rotation, or key-to-column mapping. Ensures consistent, reproducible data storage. Keywords: CSV schema, metadata, DataManager, append, auto log."
---

# Data Logging Standards

## Workflow

1. Define new fields in canonical schema constants first.
2. Keep a single internal-key to CSV-column mapping.
3. Preserve deterministic column order and header compatibility.
4. Include reproducibility metadata for context and measurement type.
5. Validate append-mode headers before writing rows.
6. Keep write paths thread-safe and close files cleanly.

## Validation

- Schema and mapping are updated together.
- Append mode rejects incompatible headers.
- New or changed fields have regression test coverage.
- Flush and close behavior is verified.

## Common Mistakes

- Ad hoc columns introduced only in write code.
- Silent header drift across runs.
- Unit changes without column name updates.

## Project Anchors

- [CSV field schema](v3/core/constants.py#L92)
- [Internal to CSV key map](v3/core/constants.py#L132)
- [Auto-log schema](v3/core/constants.py#L169)
- [DataManager class](v3/core/data_manager.py#L50)
- [initialize_file lifecycle](v3/core/data_manager.py#L178)
- [append-mode open and header checks](v3/core/data_manager.py#L274)
- [single row write path](v3/core/data_manager.py#L430)
- [DataManager metadata test](v3/tests/test_data_manager.py#L289)
- [Auto logging behavior test suite](v3/tests/test_auto_logging_behavior.py#L1)
