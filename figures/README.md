# GridPulse figures

README figures are code-derived analytical evidence.

The current repository still commits the two synthetic development SVGs:

- `demo_demand_forecast.svg`
- `demo_stress_timeline.svg`

`scripts/generate_readme_figures.py` has been upgraded to generate three real PJM EIA-930 figures from the prepared 2022–2025 local dataset:

- `pjm_2025_peak_demand_forecast.svg`
- `pjm_2025_forecast_benchmark.svg`
- `pjm_2025_june_generation_mix.svg`

Those three real-data SVG outputs are **not committed yet**, so the top-level README should not reference them as if they are already present.

After running the generator against the frozen processed dataset, review the outputs, commit the SVGs, then replace the synthetic README visual section with the real PJM evidence.
