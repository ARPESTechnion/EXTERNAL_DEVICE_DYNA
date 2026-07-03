# Skill 06: Data Logging Standards and Reproducibility

## Activate When

- Adding/modifying CSV fields, metadata rows, append/new-file behavior, or auto-logging.
- Changing internal measurement keys or export formats.

## Mandatory Development Steps

1. Define every new field in canonical schema/constants before writing data.
2. Keep one explicit mapping from internal keys to persisted column names.
3. Preserve deterministic column order and header integrity.
4. Include sufficient metadata for reproducibility (measurement type, notes, context).
5. Ensure append mode validates existing header schema before writing.
6. Keep logging thread-safe and bounded where live buffering is used.
7. Flush/close resources cleanly on end, abort, and error paths.

## Validation and Review Requirements

- Header equality check enforced for append mode.
- New field appears in schema, mapping, and at least one test.
- Unit and naming consistency reviewed across columns.
- Rotation and size policies verified for long sessions.

## Common Mistakes to Avoid

- Adding columns ad hoc in write paths without schema update.
- Silent header drift between runs.
- Writing mixed units under unchanged column names.
- Losing metadata when changing measurement types.

## In-Project Examples

- `v3/core/constants.py`: `CSV_FIELDNAMES`, `DATA_KEY_TO_CSV`, `AUTO_LOG_FIELDNAMES`.
- `v3/core/data_manager.py`: header validation, file lifecycle, auto-log rotation.
- `v3/tests/test_data_manager.py` and `v3/tests/test_auto_logging_behavior.py`: logging behavior checks.

## Quick Mode (Token Lite)

- Schema and key-map updated together.
- Append header validation preserved.
- One regression test for new/changed field.
- Close/flush path verified.
