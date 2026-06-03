# BSIM4 NMOS dynamic strain evaluation

Generated: 2026-06-03 13:30 UTC

## Overview

This report compares simulations **without** the strain wrapper (baseline device only)
and **with** the generated strain-aware wrapper subcircuit.

- Device netlist: `/mnt/d/proj/strained-device-model/models/bsim4_nmos.subckt`
- Wrapper output directory: `/mnt/d/proj/strained-device-model/results/bsim4_nmos_dynamic`

## Strain model parameters

| Parameter | Value | Description |
| --- | --- | --- |
| ν | 0.47 | Substrate Poisson's ratio |
| β | 0.8 | Threshold voltage sensitivity |
| γ | 0.0 | Mobility sensitivity |
| Vth0 | 0.4 | Unstrained threshold reference |
| μ0 | 0.04 | Unstrained mobility reference |

## Dynamic device model parameters

| Parameter | Value | Description |
| --- | --- | --- |
| τ_m | 0.05 | Mechanical low-pass time constant [s] (Option 2) |
| β_r | 2.0 | Threshold strain-rate sensitivity (Option 3) |
| γ_r | 0.0 | Mobility strain-rate sensitivity (Option 3) |
| Hysteresis | enabled | Asymmetric load/unload tracking (Option 4) |
| τ_load | 0.02 | Channel-strain loading time constant [s] |
| τ_unload | 0.1 | Channel-strain unloading time constant [s] |

## Summary metrics

| Case | Baseline &#124;I_D&#124; [A] | Strained &#124;I_D&#124; [A] | Relative change [%] |
| --- | --- | --- | --- |
| Strain magnitude sweep | 0.00024057 | 0.000251412 | 4.507 |
| Strain direction sweep (mean) | 0.00024057 | 0.000243452 | 1.198 |

## Figures

### Drain current vs applied strain

![Drain current vs applied strain](figures/magnitude_comparison.svg)

### Drain current vs force direction

![Drain current vs force direction](figures/direction_comparison.svg)

### Strain-induced parameter shifts

![Strain-induced parameter shifts](figures/strain_controls.svg)

### Transfer characteristics

![Transfer characteristics](figures/transfer_comparison.svg)

### Dynamic transient response

![Dynamic transient response](figures/transient_comparison.svg)

### Dynamic parameter shifts

![Dynamic parameter shifts](figures/transient_controls.svg)

## Strain magnitude sweep data (sample)

| v-sweep | v(eps_s) | v(alpha) | vdd#branch |
| --- | --- | --- | --- |
| 0 | 0 | 0 | -0.00024057 |
| 0.0005 | 0.0005 | 0 | -0.000241645 |
| 0.001 | 0.001 | 0 | -0.000242723 |
| 0.002 | 0.002 | 0 | -0.000244884 |
| 0.0025 | 0.0025 | 0 | -0.000245967 |
| 0.0035 | 0.0035 | 0 | -0.00024814 |
| 0.004 | 0.004 | 0 | -0.000249229 |
| 0.005 | 0.005 | 0 | -0.000251412 |

## Strain direction sweep data (sample)

| v-sweep | v(eps_s) | v(alpha) | vdd#branch |
| --- | --- | --- | --- |
| 0 | 0.005 | 0 | -0.000251412 |
| 0.19635 | 0.005 | 0.19635 | -0.000250801 |
| 0.392699 | 0.005 | 0.392699 | -0.000249062 |
| 0.589049 | 0.005 | 0.589049 | -0.000246469 |
| 0.883573 | 0.005 | 0.883573 | -0.000241878 |
| 1.07992 | 0.005 | 1.07992 | -0.000239032 |
| 1.27627 | 0.005 | 1.27627 | -0.000236863 |
| 1.5708 | 0.005 | 1.5708 | -0.000235542 |

## Transfer sweep notes

- ε_S = 0.000%: peak |I_D| baseline = 0.00202137 A, strained = 0.00202137 A, Δ = 0.00%
- ε_S = 0.250%: peak |I_D| baseline = 0.00202137 A, strained = 0.00203077 A, Δ = 0.47%
- ε_S = 0.500%: peak |I_D| baseline = 0.00202137 A, strained = 0.00204018 A, Δ = 0.93%

## Transient strain profile notes

- Profile: `sine` (amplitude = 0.500%, frequency = 0.3 Hz)
- Simulation window: 0 to 5 s (step = 0.01 s)
- Peak |I_D| baseline = 0.00024057 A, strained = 0.00024057 A, Δ = 0.00%

## How to reproduce

```bash
strain-spice run --device /mnt/d/proj/strained-device-model/models/bsim4_nmos.subckt --config <your-config.yaml> --output /mnt/d/proj/strained-device-model/results/bsim4_nmos_dynamic
```
