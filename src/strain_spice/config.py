"""Configuration models for strain SPICE workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DeviceConfig:
    """User device and port mapping."""

    subckt: str | None = None
    ports: list[str] = field(default_factory=lambda: ["d", "g", "s"])
    gate_port: str = "g"
    drain_port: str = "d"
    source_port: str = "s"
    bulk_port: str | None = "b"
    mobility_control_port: str | None = "dmu_ctrl"
    instance_params: dict[str, float | str] = field(default_factory=dict)


@dataclass
class StrainParams:
    """Mechanical and electrical strain coefficients."""

    nu: float = 0.47
    beta: float = 1.0
    gamma: float = 0.05
    vth0: float = 0.5
    mu0: float = 0.01


@dataclass
class HysteresisConfig:
    """Asymmetric load/unload tracking on channel strain (Option 4)."""

    enabled: bool = False
    tau_load: float = 0.05
    tau_unload: float = 0.20


@dataclass
class DynamicStrainConfig:
    """Dynamic extensions to the static Liu et al. strain map."""

    mechanical_tau: float = 0.0
    beta_r: float = 0.0
    gamma_r: float = 0.0
    hysteresis: HysteresisConfig = field(default_factory=HysteresisConfig)


@dataclass
class StrainProfileConfig:
    """Time-varying applied strain profile for transient simulation (Option 1)."""

    type: str = "sine"
    amplitude: float = 0.005
    frequency: float = 0.3
    offset: float = 0.0
    alpha: float = 0.0
    alpha_rate: float = 0.0


@dataclass
class TransientConfig:
    """Transient testbench settings."""

    enabled: bool = False
    tstop: float = 5.0
    tstep: float = 0.01
    profile: StrainProfileConfig = field(default_factory=StrainProfileConfig)


@dataclass
class BiasConfig:
    """DC bias for testbenches."""

    vdd: float = 10.0
    vgs: float = 2.0
    vss: float = 0.0


@dataclass
class StrainMagnitudeSweep:
    """Sweep applied strain magnitude at fixed direction."""

    eps_s_max: float = 0.005
    steps: int = 11
    alpha: float = 0.0


@dataclass
class StrainDirectionSweep:
    """Sweep force direction at fixed strain magnitude."""

    eps_s: float = 0.005
    alpha_max: float = 1.5707963267948966
    steps: int = 32


@dataclass
class TransferSweep:
    """Optional Id-Vgs transfer sweep."""

    enabled: bool = True
    vgs_min: float = 0.0
    vgs_max: float = 5.0
    steps: int = 51
    eps_s_cases: list[float] = field(default_factory=lambda: [0.0, 0.0025, 0.005])
    alpha: float = 0.0


@dataclass
class SweepConfig:
    """Simulation sweep definitions."""

    strain_magnitude: StrainMagnitudeSweep = field(default_factory=StrainMagnitudeSweep)
    strain_direction: StrainDirectionSweep = field(default_factory=StrainDirectionSweep)
    transfer: TransferSweep = field(default_factory=TransferSweep)


@dataclass
class StrainSpiceConfig:
    """Top-level configuration."""

    device: DeviceConfig = field(default_factory=DeviceConfig)
    strain: StrainParams = field(default_factory=StrainParams)
    dynamic: DynamicStrainConfig = field(default_factory=DynamicStrainConfig)
    transient: TransientConfig = field(default_factory=TransientConfig)
    bias: BiasConfig = field(default_factory=BiasConfig)
    sweeps: SweepConfig = field(default_factory=SweepConfig)
    ngspice_binary: str = "ngspice"
    title: str = "Strain SPICE comparison report"

    @classmethod
    def from_yaml(cls, path: Path) -> StrainSpiceConfig:
        """Load configuration from a YAML file."""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Config file must contain a mapping: {path}")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrainSpiceConfig:
        """Build configuration from a nested dictionary."""
        device = DeviceConfig(**data.get("device", {}))
        strain = StrainParams(**data.get("strain", {}))
        bias = BiasConfig(**data.get("bias", {}))

        dynamic_raw = data.get("dynamic", {})
        hysteresis = HysteresisConfig(**dynamic_raw.get("hysteresis", {}))
        dynamic = DynamicStrainConfig(
            mechanical_tau=dynamic_raw.get("mechanical_tau", 0.0),
            beta_r=dynamic_raw.get("beta_r", 0.0),
            gamma_r=dynamic_raw.get("gamma_r", 0.0),
            hysteresis=hysteresis,
        )

        transient_raw = data.get("transient", {})
        profile = StrainProfileConfig(**transient_raw.get("profile", {}))
        transient = TransientConfig(
            enabled=transient_raw.get("enabled", False),
            tstop=transient_raw.get("tstop", 5.0),
            tstep=transient_raw.get("tstep", 0.01),
            profile=profile,
        )

        sweeps_raw = data.get("sweeps", {})
        sweeps = SweepConfig(
            strain_magnitude=StrainMagnitudeSweep(**sweeps_raw.get("strain_magnitude", {})),
            strain_direction=StrainDirectionSweep(**sweeps_raw.get("strain_direction", {})),
            transfer=TransferSweep(**sweeps_raw.get("transfer", {})),
        )

        return cls(
            device=device,
            strain=strain,
            dynamic=dynamic,
            transient=transient,
            bias=bias,
            sweeps=sweeps,
            ngspice_binary=data.get("ngspice_binary", "ngspice"),
            title=data.get("title", "Strain SPICE comparison report"),
        )
