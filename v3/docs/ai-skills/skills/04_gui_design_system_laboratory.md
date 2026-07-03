# Skill 04: GUI Design System for Laboratory Workflows

## Activate When

- Adding or modifying any Tkinter tab, widget group, status display, or plotting panel.
- Changing control workflows for measurement execution.

## Mandatory Development Steps

1. Reuse shared theme tokens from `v3/gui/theme.py` (colors, fonts, spacing).
2. Build tab UI on `BaseTab` conventions and shared components.
3. Keep UI responsive: long operations in worker paths, UI updates via event bus.
4. Provide clear instrument status visibility (LED/state text/connection controls).
5. Use non-blocking input validation for numeric controls.
6. Preserve lab workflow clarity: configure -> start -> monitor -> stop -> review.
7. Ensure layout remains usable on typical lab screen sizes and resizes.

## Validation and Review Requirements

- Visual consistency with existing tabs (spacing, labels, status strip behavior).
- No direct worker-thread reads of Tk variables.
- Connection status and error visibility are obvious without opening logs.
- Manual user flow test: setup, run, interrupt, and recover.

## Common Mistakes to Avoid

- Bypassing theme tokens with ad-hoc styles.
- Blocking UI thread during measurement operations.
- Hiding critical errors in logs only.
- Reading or mutating Tk-bound state from worker threads.

## In-Project Examples

- `v3/gui/theme.py`: canonical visual tokens.
- `v3/gui/base_tab.py`: shared tab and connection-header conventions.
- `v3/gui/components/validating_entry.py`: non-blocking validation feedback.
- `v3/core/ui_events.py` and `v3/gui/app.py`: event-driven UI updates.
- `/memories/repo/hall-offset-thread-safe.md`: Tk-thread safety lesson.

## Quick Mode (Token Lite)

- Theme tokens reused.
- Event-bus update path kept.
- Validation and status visibility present.
- UI thread remains non-blocking.
