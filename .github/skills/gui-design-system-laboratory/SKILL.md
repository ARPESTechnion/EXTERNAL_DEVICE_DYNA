---
name: gui-design-system-laboratory
description: "Use when changing Tkinter GUI tabs, controls, status indicators, and measurement workflows. Enforces v3 visual tokens, layout conventions, event-driven UI updates, and laboratory usability patterns. Keywords: tkinter tab, status LED, validation entry, results tab, UI workflow."
---

# GUI Design System for Laboratory Workflows

## Workflow

1. Reuse theme tokens for colors, spacing, and fonts.
2. Build on BaseTab and shared components for consistency.
3. Keep UI responsive by using event-driven updates from worker logic.
4. Keep instrument status visible: connection state, errors, progress.
5. Use non-blocking validation for numeric inputs.
6. Preserve lab workflow clarity: configure, run, monitor, stop, review.

## Validation

- New UI follows existing spacing and status patterns.
- No worker-thread direct access to Tk variables.
- Manual flow test passes for start, stop, and error visibility.

## Common Mistakes

- Ad hoc styles instead of theme tokens.
- Blocking the UI thread during measurement operations.
- Hiding critical failures only in logs.

## Project Anchors

- [Theme token palette](v3/gui/theme.py#L9)
- [Theme apply entry point](v3/gui/theme.py#L52)
- [ConnectionHeader pattern](v3/gui/base_tab.py#L53)
- [BaseTab contract](v3/gui/base_tab.py#L122)
- [ValidatingEntry widget](v3/gui/components/validating_entry.py#L52)
- [UIEventBus post](v3/core/ui_events.py#L57)
- [UIEventBus drain](v3/core/ui_events.py#L77)
- Hall offset thread-safety memory: /memories/repo/hall-offset-thread-safe.md line 1
