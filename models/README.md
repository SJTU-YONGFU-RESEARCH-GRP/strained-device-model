# Evaluation device models

Reference MOS subcircuits for strain-wrapper evaluation with ngspice.

| Model file | Type | ngspice level | Description |
|------------|------|---------------|-------------|
| `bsim3_nmos.subckt` | NMOS | 8 | BSIM3v3 |
| `bsim3_pmos.subckt` | PMOS | 8 | BSIM3v3 |
| `bsim4_nmos.subckt` | NMOS | 54 | BSIM4 |
| `bsim4_pmos.subckt` | PMOS | 54 | BSIM4 |
| `bsim4l14_nmos.subckt` | NMOS | 14 | BSIM4 (alternate ngspice level-14 interface) |

Each subcircuit exposes `d g s b` and accepts instance parameters `W` and `L`.

Matching evaluation configs live in `configs/`.

## Run an evaluation

```bash
strain-spice run \
  --device models/bsim4_nmos.subckt \
  --config configs/bsim4_nmos.yaml \
  --output results/bsim4_nmos
```

BSIM models use **threshold-shift-only** strain coupling (`mobility_control_port: null` in configs).
The wrapper applies strain through the effective gate-voltage shift (`E_gshift`).

## Notes

- Model cards use generic 180 nm-class parameters suitable for relative strain comparisons, not foundry sign-off.
- Replace `W`, `L`, and model-card parameters with your PDK values when available.
- PMOS configs use negative drain/gate bias in `configs/bsim*_pmos.yaml`.
