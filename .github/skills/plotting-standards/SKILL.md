---
name: plotting-standards
description: "Use when adding or changing plots, axes, legends, fit overlays, derivative views, autoscale behavior, and graph exports in the lab GUI. Keywords: matplotlib, axis label, legend, errorbar, export PNG CSV."
---

# Plotting Standards

## Workflow

1. Label axes with quantity and unit for every plot.
2. Preserve consistent style: grid, tick direction, marker and line semantics.
3. Use legend for multi-series or multi-channel displays.
4. Keep autoscale and range controls intact and predictable.
5. Include uncertainty/error-bar behavior when data supports it.
6. Ensure export outputs preserve interpretation context.

## Validation

- Axes and legends are complete and correct.
- Plot refresh remains responsive under live updates.
- Exported files match on-screen data semantics.
- Graceful fallback exists if plotting backend is unavailable.

## Common Mistakes

- Missing units on axes.
- Inconsistent channel color semantics.
- Excessive redraw frequency causing UI lag.

## Project Anchors

- [Matplotlib backend import](v3/gui/results_tab.py#L70)
- [ResultsTab plot refresh](v3/gui/results_tab.py#L1622)
- [Graph PNG export](v3/gui/results_tab.py#L2056)
- [Graph CSV export](v3/gui/results_tab.py#L2077)
- [Dyna tab plot builder](v3/gui/dyna_tab.py#L305)
- [Dyna tab plot update](v3/gui/dyna_tab.py#L410)
- [Helmholtz tab plot builder](v3/gui/helmholtz_tab.py#L252)
- [Helmholtz tab plot update](v3/gui/helmholtz_tab.py#L328)
