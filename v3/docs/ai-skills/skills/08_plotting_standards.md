# Skill 08: Plotting and Scientific Visualization Standards

## Activate When

- Adding or modifying plots, plot controls, fitting overlays, derivatives, or exports.

## Mandatory Development Steps

1. Label every axis with quantity and unit.
2. Keep style consistent with current app defaults (grid, tick direction, marker/line usage).
3. Use legends when multiple channels/series are shown.
4. Keep autoscale and manual range controls stable and discoverable.
5. Ensure export output preserves context (labels, fitted data, uncertainty where available).
6. Handle missing plotting backend gracefully.

## Validation and Review Requirements

- Axes and legend labels are semantically correct.
- Multi-channel traces are distinguishable by color/label.
- Plot refresh path does not freeze UI at normal update rates.
- Exported PNG/CSV reproduces on-screen interpretation.

## Common Mistakes to Avoid

- Unlabeled axes or missing units.
- Inconsistent channel color meaning between graphs.
- Overly frequent redraws causing UI lag.
- Dropping uncertainty/error bars without user control.

## In-Project Examples

- `v3/gui/results_tab.py`: dual-plot workflow, labels, legends, autoscale, export, error bars/fits.
- `v3/gui/dyna_tab.py` and `v3/gui/helmholtz_tab.py`: embedded Matplotlib and fallback handling.

## Quick Mode (Token Lite)

- Axis labels + units present.
- Legend present for multi-series.
- Autoscale still works.
- Export path tested once.
