# Strain-SPICE evaluation results

Generated simulation outputs from bundled and custom `strain-spice run` jobs.
Re-run `./scripts/run_all.sh` to refresh every bundled evaluation and this index.

## How to read time-varying results

Dynamic configs (`transient.enabled: true`) add transient testbenches and figures.
Use `transient.run_all_presets: true` to exercise the built-in profile library (sine, drift, abrupt, pulse, triangle PWL, custom PWL) in one run.

- `figures/transient_comparison[_<profile>].svg` — applied strain ε_S(t) and drain current |I_D|(t)
- `figures/transient_controls[_<profile>].svg` — ΔVth and Δμ versus time
- `strain_comparison_report.md` — per-profile metrics plus a comparison table when multiple profiles run

Index last updated: 2026-06-05 08:46 UTC

## Evaluations

- **[bsim3_nmos](bsim3_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim3_nmos/figures/magnitude_comparison.svg), [direction](bsim3_nmos/figures/direction_comparison.svg)
- **[bsim3_pmos](bsim3_pmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim3_pmos/figures/magnitude_comparison.svg), [direction](bsim3_pmos/figures/direction_comparison.svg)
- **[bsim4_nmos](bsim4_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4_nmos/figures/magnitude_comparison.svg), [direction](bsim4_nmos/figures/direction_comparison.svg)
- **[bsim4_nmos_dynamic](bsim4_nmos_dynamic/strain_comparison_report.md)**
  - Time-varying (default): [|I_D|(t)](bsim4_nmos_dynamic/figures/transient_comparison.svg), [ΔVth/Δμ(t)](bsim4_nmos_dynamic/figures/transient_controls.svg), [transient CSV](bsim4_nmos_dynamic/tb_strained_transient.csv)
  - DC sweeps: [magnitude](bsim4_nmos_dynamic/figures/magnitude_comparison.svg), [direction](bsim4_nmos_dynamic/figures/direction_comparison.svg)
- **[bsim4_pmos](bsim4_pmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4_pmos/figures/magnitude_comparison.svg), [direction](bsim4_pmos/figures/direction_comparison.svg)
- **[bsim4l14_nmos](bsim4l14_nmos/strain_comparison_report.md)**
  - DC sweeps: [magnitude](bsim4l14_nmos/figures/magnitude_comparison.svg), [direction](bsim4l14_nmos/figures/direction_comparison.svg)
- **[strain_demo_spectre](strain_demo_spectre/strain_comparison_report.md)**
  - DC sweeps: [magnitude](strain_demo_spectre/figures/magnitude_comparison.svg), [direction](strain_demo_spectre/figures/direction_comparison.svg)
- **[transient_profiles_ngspice](transient_profiles_ngspice/strain_comparison_report.md)**
  - Time-varying (abrupt): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_abrupt.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_abrupt.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_abrupt.csv)
  - Time-varying (custom): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_custom.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_custom.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_custom.csv)
  - Time-varying (drift): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_drift.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_drift.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_drift.csv)
  - Time-varying (pulse): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_pulse.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_pulse.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_pulse.csv)
  - Time-varying (pwl): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_pwl.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_pwl.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_pwl.csv)
  - Time-varying (sine): [|I_D|(t)](transient_profiles_ngspice/figures/transient_comparison_sine.svg), [ΔVth/Δμ(t)](transient_profiles_ngspice/figures/transient_controls_sine.svg), [transient CSV](transient_profiles_ngspice/tb_strained_transient_sine.csv)
  - DC sweeps: [magnitude](transient_profiles_ngspice/figures/magnitude_comparison.svg), [direction](transient_profiles_ngspice/figures/direction_comparison.svg)
