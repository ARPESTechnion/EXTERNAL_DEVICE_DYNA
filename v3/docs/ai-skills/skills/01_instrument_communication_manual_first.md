# Skill 01: Instrument Communication and Manual-First Command Design

## Activate When

- Adding or changing any instrument command path (SCPI, VISA, GPIB, TCP, serial).
- Implementing startup, query/write sequencing, timeout handling, or shutdown behavior.
- Investigating communication errors, stale replies, or intermittent read failures.

## Mandatory Development Steps

1. Identify the exact instrument model and manual section before coding.
2. Define command contract per operation: `write`, `query`, expected unit/type, timeout.
3. Verify startup identity (`*IDN?` or vendor equivalent) and reject mismatches.
4. Implement protocol-safe query path (buffer hygiene, retries, bounded timeout).
5. Normalize units at the boundary (driver input/output) and document conversions.
6. Define explicit shutdown sequence to leave hardware in safe state.
7. Surface recoverable vs non-recoverable errors distinctly in logs/exceptions.

## Validation and Review Requirements

- Confirm each command string exists in manual and matches argument format.
- Test at least one successful query and one timeout/retry path.
- Validate unit round-trip for at least one source and one measurement value.
- Confirm post-failure state is clean (no stale response contaminating next query).

## Common Mistakes to Avoid

- Assuming SCPI uniformity across non-SCPI-complete devices.
- Reusing generic query flow without buffer clearing where device needs it.
- Treating partial reads as complete responses.
- Mixing engineering units silently (mA vs A, Oe vs G).
- Forgetting safe output-off or reset on disconnect.

## In-Project Examples

- `Utility/New_LockIn.py`: `_clear_buffer`, `query`, retry/backoff, SR830-specific behavior.
- `Utility/Keithley2450.py`: explicit `write`/`query`, startup identification, command grouping.
- `/memories/repo/k2450-query-interrupted-trace-reply-contamination.md`: stale-reply failure mode and fix pattern.
- `/memories/repo/sr830-auto-wait.md`: command completion polling strategy.

## Quick Mode (Token Lite)

- Manual section verified.
- Startup ID check added.
- Query path has timeout + retry + buffer strategy.
- Units documented and tested once.
- Safe shutdown path confirmed.
