"""Generate strain-aware and baseline SPICE netlists."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

from strain_spice.config import (
    BiasConfig,
    DynamicStrainConfig,
    SimulatorKind,
    StrainProfileConfig,
    StrainSpiceConfig,
)
from strain_spice.parser import SubcktDefinition
from strain_spice.strain_profiles import resolve_transient_profiles, strain_source_lines


def _repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


def _netlist_extension(simulator: SimulatorKind) -> str:
    """Return the netlist filename extension for the selected simulator."""
    return ".scs" if simulator == "spectre" else ".cir"


def _netlist_header(simulator: SimulatorKind) -> str:
    """Return a language pragma required by some simulator netlist dialects."""
    if simulator == "spectre":
        return "simulator lang=spice"
    return ""


def _include_statement(simulator: SimulatorKind, filename: str) -> str:
    """Return an include line compatible with the target simulator."""
    if simulator == "spectre":
        return f'.include "{filename}"'
    return f".include {filename}"


SPECTRE_STRAIN_DEMO_MOS = dedent(
    """
    simulator lang=spectre
    subckt strain_demo_mos d g s b
      parameters kp=2e-4 vth=0.35 lambda=0.02
      Id1 (d s) bsource i = kp*max(0, v(g)-v(s)-vth)*(1+lambda*max(0, v(d)-v(s)))
    ends strain_demo_mos
    """
).strip()


def _device_netlist_body(device: SubcktDefinition, simulator: SimulatorKind) -> str:
    """Return the device subcircuit text for the selected simulator."""
    if simulator == "spectre" and device.name == "strain_demo_mos":
        return SPECTRE_STRAIN_DEMO_MOS
    return device.body


STRAIN_ENGINE_SPICE = dedent(
    """
    .subckt strain_engine_spice eps_s alpha dvth dmu
    .param nu=0.47 beta=1.0 gamma=0.05 beta_r=0.0 gamma_r=0.0
    .param tau_m=1e-15 tau_load=1e-12 tau_unload=1e-12
    Rmech eps_s eps_s_filt 1
    Cmech eps_s_filt 0 {tau_m}
    Beps_raw n_eps_t_raw 0 V = '{ (V(eps_s_filt)/2) * (1 - nu + (1 + nu) * cos(2 * V(alpha))) }'
    Ghist n_eps_t 0 cur = '{ (V(n_eps_t_raw)-V(n_eps_t)) / ((V(n_eps_t_raw) >= V(n_eps_t)) ? tau_load : tau_unload) }'
    Chist n_eps_t 0 1
    Bdvth dvth 0 V = '{ -beta * V(n_eps_t) - beta_r * ddt(V(n_eps_t)) }'
    Bdmu dmu 0 V = '{ gamma * V(n_eps_t) + gamma_r * ddt(V(n_eps_t)) }'
    .ends strain_engine_spice
    """
).strip()


def _mechanical_tau(dynamic: DynamicStrainConfig) -> float:
    """Return the RC time constant used for the mechanical filter."""
    if dynamic.mechanical_tau <= 0.0:
        return 1e-15
    return dynamic.mechanical_tau


def _hysteresis_taus(dynamic: DynamicStrainConfig) -> tuple[float, float]:
    """Return load/unload time constants for the hysteresis state node."""
    if not dynamic.hysteresis.enabled:
        return 1e-12, 1e-12
    return max(dynamic.hysteresis.tau_load, 1e-15), max(dynamic.hysteresis.tau_unload, 1e-15)


def _strain_engine_params(config: StrainSpiceConfig) -> str:
    """Format strain-engine parameter assignments for a wrapper instance."""
    strain = config.strain
    dynamic = config.dynamic
    tau_m = _mechanical_tau(dynamic)
    tau_load, tau_unload = _hysteresis_taus(dynamic)
    return (
        f"nu={strain.nu} beta={strain.beta} gamma={strain.gamma} "
        f"beta_r={dynamic.beta_r} gamma_r={dynamic.gamma_r} "
        f"tau_m={tau_m} tau_load={tau_load} tau_unload={tau_unload}"
    )


@dataclass(frozen=True)
class TransientNetlistCase:
    """Baseline and strained transient testbenches for one strain profile."""

    slug: str
    profile: StrainProfileConfig
    baseline_tb: Path
    strained_tb: Path


@dataclass(frozen=True)
class GeneratedNetlists:
    """Paths to generated netlist artifacts."""

    output_dir: Path
    device_copy: Path
    wrapper: Path
    baseline_magnitude_tb: Path
    strained_magnitude_tb: Path
    baseline_direction_tb: Path
    strained_direction_tb: Path
    baseline_transfer_tbs: list[Path]
    strained_transfer_tbs: list[Path]
    transient_cases: list[TransientNetlistCase] = field(default_factory=list)

    @property
    def baseline_transient_tb(self) -> Path | None:
        """Return the first baseline transient testbench, if any."""
        if not self.transient_cases:
            return None
        return self.transient_cases[0].baseline_tb

    @property
    def strained_transient_tb(self) -> Path | None:
        """Return the first strained transient testbench, if any."""
        if not self.transient_cases:
            return None
        return self.transient_cases[0].strained_tb


def _format_instance_params(params: dict[str, float | str]) -> str:
    """Format ngspice instance parameter assignments."""
    if not params:
        return ""
    assignments = " ".join(f"{key}={value}" for key, value in params.items())
    return f" {assignments}"


def _strain_engine_instance(config: StrainSpiceConfig, simulator: SimulatorKind) -> str:
    """Return the strain-engine instance line for the selected simulator."""
    params = _strain_engine_params(config)
    if simulator == "spectre":
        return f"Xse (eps_s alpha dvth dmu) strain_engine {params}"
    return f"Xse eps_s alpha dvth dmu strain_engine_spice {params}"


def _gate_shift_line(simulator: SimulatorKind) -> str:
    """Return the gate voltage-shift element for the wrapper subcircuit."""
    if simulator == "spectre":
        return "E_gshift (g_eff g) vsource v = -v(dvth)"
    return "E_gshift g_eff g dvth 0 -1"


def _device_instance_line(
    device: SubcktDefinition,
    config: StrainSpiceConfig,
    simulator: SimulatorKind,
    *,
    gate_node: str = "g_eff",
) -> str:
    """Return the wrapped user-device instance line."""
    device_cfg = config.device
    mobility_port = device_cfg.mobility_control_port
    ports = [device_cfg.drain_port, gate_node, device_cfg.source_port]
    if device_cfg.bulk_port:
        ports.append(device_cfg.bulk_port)
    if mobility_port is not None:
        ports.append(mobility_port)
    joined_ports = " ".join(ports)
    params = _format_instance_params(device_cfg.instance_params)
    if simulator == "spectre":
        return f"Xdev ({joined_ports}) {device.name}{params}"
    return f"Xdev {joined_ports} {device.name}{params}"


def _wrapper_subckt(
    device: SubcktDefinition,
    config: StrainSpiceConfig,
    simulator: SimulatorKind,
) -> str:
    """Build the strain-aware wrapper subcircuit."""
    strain = config.strain
    engine = _strain_engine_instance(config, simulator)
    gate_shift = _gate_shift_line(simulator)
    device_instance = _device_instance_line(device, config, simulator)
    tau_load, tau_unload = _hysteresis_taus(config.dynamic)

    if simulator == "spectre":
        return dedent(
            f"""
            simulator lang=spectre
            ahdl_include "strain_engine.va"
            subckt strain_aware_device d g s b eps_s alpha
              parameters nu={strain.nu} beta={strain.beta} gamma={strain.gamma} vth0={strain.vth0} mu0={strain.mu0}
              parameters beta_r={config.dynamic.beta_r} gamma_r={config.dynamic.gamma_r} tau_m={_mechanical_tau(config.dynamic)}
              parameters tau_load={tau_load} tau_unload={tau_unload}
              {engine}
              {gate_shift}
              {device_instance}
            ends strain_aware_device
            """
        ).strip()

    return dedent(
        f"""
        .subckt strain_aware_device d g s b eps_s alpha
        .param nu={strain.nu} beta={strain.beta} gamma={strain.gamma} vth0={strain.vth0} mu0={strain.mu0}
        .param beta_r={config.dynamic.beta_r} gamma_r={config.dynamic.gamma_r} tau_m={_mechanical_tau(config.dynamic)}
        .param tau_load={tau_load} tau_unload={tau_unload}
        {engine}
        {gate_shift}
        {device_instance}
        .ends strain_aware_device
        """
    ).strip()


def _common_bias(bias: BiasConfig) -> str:
    """Return shared bias source declarations."""
    return dedent(
        f"""
        Vdd d 0 dc {bias.vdd}
        Vgs g 0 dc {bias.vgs}
        Vss s 0 dc {bias.vss}
        Vbb b 0 dc {bias.vss}
        """
    ).strip()


def _baseline_instance(device: SubcktDefinition, config: StrainSpiceConfig) -> str:
    """Instantiate the unwrapped user device."""
    device_cfg = config.device
    ports = " ".join(
        port
        for port in (
            device_cfg.drain_port,
            device_cfg.gate_port,
            device_cfg.source_port,
            device_cfg.bulk_port,
            device_cfg.mobility_control_port,
        )
        if port is not None
    )
    return f"Xdev {ports} {device.name}{_format_instance_params(device_cfg.instance_params)}"


def _strained_instance(config: StrainSpiceConfig) -> str:
    """Instantiate the strain-aware wrapper."""
    strain = config.strain
    return (
        "Xwrap d g s b eps_s alpha strain_aware_device "
        f"nu={strain.nu} beta={strain.beta} gamma={strain.gamma} "
        f"vth0={strain.vth0} mu0={strain.mu0} {_strain_engine_params(config)}"
    )


def _strain_source_lines(profile: StrainProfileConfig, *, tstop: float) -> tuple[str, str]:
    """Return SPICE source declarations for applied strain and angle."""
    return strain_source_lines(profile, tstop=tstop)


def _transient_testbench(
    *,
    simulator: SimulatorKind,
    include_files: list[str],
    instance_line: str,
    bias: str,
    mobility_bias: str,
    profile: StrainProfileConfig,
    tstop: float,
    tstep: float,
    title: str,
    wrapped: bool,
) -> str:
    """Build a transient simulation testbench with time-varying strain inputs."""
    header = _netlist_header(simulator)
    includes = "\n".join(_include_statement(simulator, name) for name in include_files)
    eps_source, alpha_source = _strain_source_lines(profile, tstop=tstop)
    print_vars = ["time", "v(eps_s)", "v(alpha)", "i(Vdd)"]

    sections = [
        header,
        f"* {title}",
        includes,
        eps_source,
        alpha_source,
        bias,
        instance_line,
        f".tran {tstep} {tstop}",
        f".print tran {' '.join(print_vars)}",
        ".end",
    ]
    if not wrapped:
        sections.insert(6, mobility_bias)
    return "\n".join(section for section in sections if section) + "\n"


def _step_size(total: float, steps: int) -> float:
    """Compute a positive sweep step size."""
    if steps <= 1:
        return total if total > 0 else 1.0
    return total / (steps - 1)


def _dc_testbench(
    *,
    simulator: SimulatorKind,
    include_files: list[str],
    instance_line: str,
    bias: str,
    mobility_bias: str,
    sweep_source: str,
    sweep_node: str,
    sweep_start: float,
    sweep_stop: float,
    sweep_step: float,
    fixed_sources: list[tuple[str, str, float]],
    title: str,
) -> str:
    """Build a generic DC sweep testbench."""
    header = _netlist_header(simulator)
    includes = "\n".join(_include_statement(simulator, name) for name in include_files)
    fixed = "\n".join(f"{name} {node} 0 dc {value}" for name, node, value in fixed_sources)
    sweep_decl = ""
    if sweep_node not in {node for _, node, _ in fixed_sources}:
        sweep_decl = f"{sweep_source} {sweep_node} 0 dc {sweep_start}"

    print_vars = ["v(eps_s)", "v(alpha)", "i(Vdd)"]
    sections = [
        header,
        f"* {title}",
        includes,
        sweep_decl,
        fixed,
        bias,
        mobility_bias,
        instance_line,
        f".dc {sweep_source} {sweep_start} {sweep_stop} {sweep_step}",
        f".print dc {' '.join(print_vars)}",
        ".end",
    ]
    return "\n".join(section for section in sections if section) + "\n"


def _transfer_testbench(
    *,
    simulator: SimulatorKind,
    include_files: list[str],
    instance_line: str,
    bias: str,
    mobility_bias: str,
    vgs_min: float,
    vgs_max: float,
    vgs_step: float,
    eps_s: float,
    alpha: float,
    title: str,
    wrapped: bool,
) -> str:
    """Build a single Vgs transfer sweep testbench."""
    header = _netlist_header(simulator)
    includes = "\n".join(_include_statement(simulator, name) for name in include_files)
    if wrapped:
        sections = [
            header,
            f"* {title}",
            includes,
            f"Veps eps_s 0 dc {eps_s}",
            f"Valp alpha 0 dc {alpha}",
            bias,
            instance_line,
            f".dc Vgs {vgs_min} {vgs_max} {vgs_step}",
            ".print dc v(eps_s) v(g) i(Vdd)",
            ".end",
        ]
        return "\n".join(section for section in sections if section) + "\n"

    sections = [
        header,
        f"* {title}",
        includes,
        bias,
        mobility_bias,
        instance_line,
        f".dc Vgs {vgs_min} {vgs_max} {vgs_step}",
        ".print dc v(g) i(Vdd)",
        ".end",
    ]
    return "\n".join(section for section in sections if section) + "\n"


def generate_netlists(
    device: SubcktDefinition,
    device_source_path: Path,
    config: StrainSpiceConfig,
    output_dir: Path,
) -> GeneratedNetlists:
    """Generate baseline and strained testbench netlists."""
    output_dir.mkdir(parents=True, exist_ok=True)
    simulator = config.normalized_simulator()
    suffix = _netlist_extension(simulator)

    device_body = _device_netlist_body(device, simulator)
    device_copy = output_dir / device_source_path.name
    device_copy.write_text(device_body + "\n", encoding="utf-8")

    wrapper_path = output_dir / "strain_wrap.inc"
    wrapper_parts: list[str] = [device_body, _wrapper_subckt(device, config, simulator)]
    if simulator == "ngspice":
        wrapper_parts.insert(0, STRAIN_ENGINE_SPICE)
    else:
        va_source = _repo_root() / "va" / "strain_engine.va"
        va_copy = output_dir / "strain_engine.va"
        va_copy.write_text(va_source.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper_path.write_text("\n\n".join(wrapper_parts) + "\n", encoding="utf-8")

    bias = _common_bias(config.bias)
    mobility_port = config.device.mobility_control_port
    mobility_bias = f"Vdmu {mobility_port} 0 dc 0" if mobility_port is not None else ""

    magnitude = config.sweeps.strain_magnitude
    direction = config.sweeps.strain_direction
    transfer = config.sweeps.transfer

    baseline_magnitude = output_dir / f"tb_baseline_magnitude{suffix}"
    strained_magnitude = output_dir / f"tb_strained_magnitude{suffix}"
    baseline_direction = output_dir / f"tb_baseline_direction{suffix}"
    strained_direction = output_dir / f"tb_strained_direction{suffix}"

    baseline_magnitude.write_text(
        _dc_testbench(
            simulator=simulator,
            include_files=[device_copy.name],
            instance_line=_baseline_instance(device, config),
            bias=bias,
            mobility_bias=mobility_bias,
            sweep_source="Veps",
            sweep_node="eps_s",
            sweep_start=0.0,
            sweep_stop=magnitude.eps_s_max,
            sweep_step=_step_size(magnitude.eps_s_max, magnitude.steps),
            fixed_sources=[("Valp", "alpha", magnitude.alpha)],
            title="baseline strain magnitude",
        ),
        encoding="utf-8",
    )

    strained_magnitude.write_text(
        _dc_testbench(
            simulator=simulator,
            include_files=["strain_wrap.inc"],
            instance_line=_strained_instance(config),
            bias=bias,
            mobility_bias="",
            sweep_source="Veps",
            sweep_node="eps_s",
            sweep_start=0.0,
            sweep_stop=magnitude.eps_s_max,
            sweep_step=_step_size(magnitude.eps_s_max, magnitude.steps),
            fixed_sources=[("Valp", "alpha", magnitude.alpha)],
            title="strained magnitude",
        ),
        encoding="utf-8",
    )

    baseline_direction.write_text(
        _dc_testbench(
            simulator=simulator,
            include_files=[device_copy.name],
            instance_line=_baseline_instance(device, config),
            bias=bias,
            mobility_bias=mobility_bias,
            sweep_source="Valp",
            sweep_node="alpha",
            sweep_start=0.0,
            sweep_stop=direction.alpha_max,
            sweep_step=_step_size(direction.alpha_max, direction.steps),
            fixed_sources=[("Veps", "eps_s", direction.eps_s)],
            title="baseline strain direction",
        ),
        encoding="utf-8",
    )

    strained_direction.write_text(
        _dc_testbench(
            simulator=simulator,
            include_files=["strain_wrap.inc"],
            instance_line=_strained_instance(config),
            bias=bias,
            mobility_bias="",
            sweep_source="Valp",
            sweep_node="alpha",
            sweep_start=0.0,
            sweep_stop=direction.alpha_max,
            sweep_step=_step_size(direction.alpha_max, direction.steps),
            fixed_sources=[("Veps", "eps_s", direction.eps_s)],
            title="strained direction",
        ),
        encoding="utf-8",
    )

    transfer_bias = dedent(
        f"""
        Vdd d 0 dc {config.bias.vdd}
        Vgs g 0 dc 0
        Vss s 0 dc {config.bias.vss}
        Vbb b 0 dc {config.bias.vss}
        """
    ).strip()

    baseline_transfer_tbs: list[Path] = []
    strained_transfer_tbs: list[Path] = []
    if transfer.enabled:
        vgs_step = _step_size(transfer.vgs_max - transfer.vgs_min, transfer.steps)
        for index, eps_s in enumerate(transfer.eps_s_cases):
            baseline_path = output_dir / f"tb_baseline_transfer_{index}{suffix}"
            strained_path = output_dir / f"tb_strained_transfer_{index}{suffix}"
            baseline_path.write_text(
                _transfer_testbench(
                    simulator=simulator,
                    include_files=[device_copy.name],
                    instance_line=_baseline_instance(device, config),
                    bias=transfer_bias,
                    mobility_bias=mobility_bias,
                    vgs_min=transfer.vgs_min,
                    vgs_max=transfer.vgs_max,
                    vgs_step=vgs_step,
                    eps_s=eps_s,
                    alpha=transfer.alpha,
                    title=f"baseline transfer eps_s={eps_s}",
                    wrapped=False,
                ),
                encoding="utf-8",
            )
            strained_path.write_text(
                _transfer_testbench(
                    simulator=simulator,
                    include_files=["strain_wrap.inc"],
                    instance_line=_strained_instance(config),
                    bias=transfer_bias,
                    mobility_bias="",
                    vgs_min=transfer.vgs_min,
                    vgs_max=transfer.vgs_max,
                    vgs_step=vgs_step,
                    eps_s=eps_s,
                    alpha=transfer.alpha,
                    title=f"strained transfer eps_s={eps_s}",
                    wrapped=True,
                ),
                encoding="utf-8",
            )
            baseline_transfer_tbs.append(baseline_path)
            strained_transfer_tbs.append(strained_path)

    transient_cases: list[TransientNetlistCase] = []
    if config.transient.enabled:
        resolved = resolve_transient_profiles(config.transient)
        legacy_names = (
            not config.transient.run_all_presets
            and not config.transient.profiles
            and len(resolved) == 1
        )
        for case in resolved:
            if legacy_names:
                baseline_path = output_dir / f"tb_baseline_transient{suffix}"
                strained_path = output_dir / f"tb_strained_transient{suffix}"
            else:
                baseline_path = output_dir / f"tb_baseline_transient_{case.slug}{suffix}"
                strained_path = output_dir / f"tb_strained_transient_{case.slug}{suffix}"
            baseline_path.write_text(
                _transient_testbench(
                    simulator=simulator,
                    include_files=[device_copy.name],
                    instance_line=_baseline_instance(device, config),
                    bias=bias,
                    mobility_bias=mobility_bias,
                    profile=case.profile,
                    tstop=config.transient.tstop,
                    tstep=config.transient.tstep,
                    title=f"baseline transient strain profile ({case.slug})",
                    wrapped=False,
                ),
                encoding="utf-8",
            )
            strained_path.write_text(
                _transient_testbench(
                    simulator=simulator,
                    include_files=["strain_wrap.inc"],
                    instance_line=_strained_instance(config),
                    bias=bias,
                    mobility_bias="",
                    profile=case.profile,
                    tstop=config.transient.tstop,
                    tstep=config.transient.tstep,
                    title=f"strained transient strain profile ({case.slug})",
                    wrapped=True,
                ),
                encoding="utf-8",
            )
            transient_cases.append(
                TransientNetlistCase(
                    slug=case.slug,
                    profile=case.profile,
                    baseline_tb=baseline_path,
                    strained_tb=strained_path,
                )
            )

    return GeneratedNetlists(
        output_dir=output_dir,
        device_copy=device_copy,
        wrapper=wrapper_path,
        baseline_magnitude_tb=baseline_magnitude,
        strained_magnitude_tb=strained_magnitude,
        baseline_direction_tb=baseline_direction,
        strained_direction_tb=strained_direction,
        baseline_transfer_tbs=baseline_transfer_tbs,
        strained_transfer_tbs=strained_transfer_tbs,
        transient_cases=transient_cases,
    )
