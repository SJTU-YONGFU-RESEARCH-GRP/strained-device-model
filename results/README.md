# Strain-SPICE evaluation results

Generated simulation outputs from bundled and custom `strain-spice run` jobs.
Re-run `./scripts/run_all.sh` to refresh every bundled evaluation and this index.

## How to read time-varying results

Dynamic configs (`transient.enabled: true`) add transient testbenches and figures:

- `figures/transient_comparison.svg` — applied strain ε_S(t) and drain current |I_D|(t)
- `figures/transient_controls.svg` — ΔVth and Δμ versus time
- `strain_comparison_report.md` — transient summary metrics, phase lag, and a time-series sample

Index last updated: 2026-06-03 14:10 UTC

## Evaluations

- **[bsim3_nmos](bsim3_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim3_nmos/figures/magnitude_comparison.svg), [direction](bsim3_nmos/figures/direction_comparison.svg)
- **[bsim3_pmos](bsim3_pmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim3_pmos/figures/magnitude_comparison.svg), [direction](bsim3_pmos/figures/direction_comparison.svg)
- **[bsim4_nmos](bsim4_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4_nmos/figures/magnitude_comparison.svg), [direction](bsim4_nmos/figures/direction_comparison.svg)
- **[bsim4_nmos_dynamic](bsim4_nmos_dynamic/strain_comparison_report.md)**
  - Time-varying: [|I_D|(t)](bsim4_nmos_dynamic/figures/transient_comparison.svg), [ΔVth/Δμ(t)](bsim4_nmos_dynamic/figures/transient_controls.svg), [transient CSV](bsim4_nmos_dynamic/tb_strained_transient.csv)
  - DC sweeps: [magnitude](bsim4_nmos_dynamic/figures/magnitude_comparison.svg), [direction](bsim4_nmos_dynamic/figures/direction_comparison.svg)
- **[bsim4_pmos](bsim4_pmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4_pmos/figures/magnitude_comparison.svg), [direction](bsim4_pmos/figures/direction_comparison.svg)
- **[bsim4l14_nmos](bsim4l14_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4l14_nmos/figures/magnitude_comparison.svg), [direction](bsim4l14_nmos/figures/direction_comparison.svg)
