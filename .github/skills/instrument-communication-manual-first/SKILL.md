---
name: instrument-communication-manual-first
description: "Use when implementing or reviewing instrument communication paths (SCPI, VISA, GPIB, serial, TCP), including command verification from manuals, write/query/read sequencing, timeouts, stale-buffer handling, and safe startup/shutdown. Keywords: SCPI, VISA, GPIB, timeout, query interrupted, instrument manual, buffer."
---

# Instrument Communication and Manual-First Command Design

## Workflow

1. Identify exact instrument model and relevant manual section before coding.
2. Define command contract per call: command string, transport method (write/query), expected response type, expected unit, timeout.
3. Verify connection identity at startup (for example ID query).
4. Implement robust query flow: stale-buffer protection where needed, retry strategy, bounded timeout.
5. Normalize units at the driver boundary and log conversion assumptions.
6. Define explicit safe shutdown sequence for disconnect/error paths.

## Validation

- Every command added has a manual reference or known vendor API reference.
- At least one success query and one retry or timeout path are tested.
- No stale response leaks into the next query.
- Output is safely disabled on failure exit path.

## Common Mistakes

- Assuming every device is fully SCPI-compatible.
- Treating short reads as complete responses.
- Missing buffer clear logic on devices that require it.
- Mixing units silently (mA vs A, Oe vs G).

## Project Anchors

- [SR830 stale-buffer clear](Utility/New_LockIn.py#L78)
- [SR830 synchronized query flow](Utility/New_LockIn.py#L96)
- [Keithley2450 low-level write](Utility/Keithley2450.py#L41)
- [Keithley2450 low-level query](Utility/Keithley2450.py#L45)
- [Measurement-side safe division guard](v3/core/measurements.py#L91)
- Query-interrupted contamination memory: /memories/repo/k2450-query-interrupted-trace-reply-contamination.md line 1
- SR830 auto-wait memory: /memories/repo/sr830-auto-wait.md line 1
