# BSIM4 PMOS strain evaluation

Generated: 2026-06-05 08:46 UTC

## Overview

This report compares simulations **without** the strain wrapper (baseline device only)
and **with** the generated strain-aware wrapper subcircuit.

- Device netlist: `/home/yongfu/proj/strained-device-model/models/bsim4_pmos.subckt`
- Wrapper output directory: `/home/yongfu/proj/strained-device-model/results/bsim4_pmos`

## Strain model parameters

| Parameter | Value | Description |
| --- | --- | --- |
| ν | 0.47 | Substrate Poisson's ratio |
| β | 0.8 | Threshold voltage sensitivity |
| γ | 0.0 | Mobility sensitivity |
| Vth0 | 0.42 | Unstrained threshold reference |
| μ0 | 0.015 | Unstrained mobility reference |

## Dynamic device model parameters

| Parameter | Value | Description |
| --- | --- | --- |
| τ_m | 0.0 | Mechanical low-pass time constant [s] (Option 2) |
| β_r | 0.0 | Threshold strain-rate sensitivity (Option 3) |
| γ_r | 0.0 | Mobility strain-rate sensitivity (Option 3) |
| Hysteresis | disabled | Asymmetric load/unload tracking (Option 4) |
| τ_load | 0.05 | Channel-strain loading time constant [s] |
| τ_unload | 0.2 | Channel-strain unloading time constant [s] |

## Summary metrics

| Case | Baseline &#124;I_D&#124; [A] | Strained &#124;I_D&#124; [A] | Relative change [%] |
| --- | --- | --- | --- |
| Strain magnitude sweep | 6.2123e-05 | 5.86847e-05 | -5.535 |
| Strain direction sweep (mean) | 6.2123e-05 | 6.12167e-05 | -1.459 |

## Figures

### Drain current vs applied strain

![Drain current vs applied strain](figures/magnitude_comparison.svg)

### Drain current vs force direction

![Drain current vs force direction](figures/direction_comparison.svg)

### Strain-induced parameter shifts

![Strain-induced parameter shifts](figures/strain_controls.svg)

### Transfer characteristics

![Transfer characteristics](figures/transfer_comparison.svg)

## Strain magnitude sweep data (sample)

| v-sweep | v(eps_s) | v(alpha) | vdd#branch |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 6.2123e-05 |
| 0.0005 | 0.0005 | 0 | 6.17739e-05 |
| 0.001 | 0.001 | 0 | 6.14268e-05 |
| 0.002 | 0.002 | 0 | 6.07349e-05 |
| 0.0025 | 0.0025 | 0 | 6.03905e-05 |
| 0.0035 | 0.0035 | 0 | 5.9705e-05 |
| 0.004 | 0.004 | 0 | 5.93638e-05 |
| 0.005 | 0.005 | 0 | 5.86847e-05 |

## Strain direction sweep data (sample)

| v-sweep | v(eps_s) | v(alpha) | vdd#branch |
| --- | --- | --- | --- |
| 0 | 0.005 | 0 | 5.86847e-05 |
| 0.19635 | 0.005 | 0.19635 | 5.88742e-05 |
| 0.392699 | 0.005 | 0.392699 | 5.94158e-05 |
| 0.589049 | 0.005 | 0.589049 | 6.02315e-05 |
| 0.883573 | 0.005 | 0.883573 | 6.16992e-05 |
| 1.07992 | 0.005 | 1.07992 | 6.26246e-05 |
| 1.27627 | 0.005 | 1.27627 | 6.33379e-05 |
| 1.5708 | 0.005 | 1.5708 | 6.37758e-05 |

## Transfer sweep notes

- ε_S = 0.000%: peak |I_D| baseline = 0.000824939 A, strained = 0.000824939 A, Δ = 0.00%
- ε_S = 0.250%: peak |I_D| baseline = 0.000824939 A, strained = 0.000820462 A, Δ = -0.54%
- ε_S = 0.500%: peak |I_D| baseline = 0.000824939 A, strained = 0.000815992 A, Δ = -1.08%

## How to reproduce

```bash
strain-spice run --device /home/yongfu/proj/strained-device-model/models/bsim4_pmos.subckt --config <your-config.yaml> --output /home/yongfu/proj/strained-device-model/results/bsim4_pmos
```
