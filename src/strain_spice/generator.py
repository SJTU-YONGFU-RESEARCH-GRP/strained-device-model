"""Generate strain-aware and baseline SPICE netlists."""

from __future__ import annotations

from dataclasses import dataclass
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
        return f'include "{filename}"'
    return f".include {filename}"


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
    baseline_transient_tb: Path | None = None
    strained_transient_tb: Path | None = None


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
        return f"Xse eps_s alpha dvth dmu strain_engine {params}"
    return f"Xse eps_s alpha dvth dmu strain_engine_spice {params}"


def _wrapper_subckt(
    device: SubcktDefinition,
    config: StrainSpiceConfig,
    simulator: SimulatorKind,
) -> str:
    """Build the strain-aware wrapper subcircuit."""
    device_cfg = config.device
    strain = config.strain
    mobility_port = device_cfg.mobility_control_port

    device_instance = (
        f"Xdev {device_cfg.drain_port} g_eff {device_cfg.source_port}"
        f"{f' {device_cfg.bulk_port}' if device_cfg.bulk_port else ''}"
    )
    if mobility_port is not None:
        device_instance += " dmu"

    device_instance += f" {device.name}{_format_instance_params(device_cfg.instance_params)}"
    engine = _strain_engine_instance(config, simulator)
    ahdl = 'ahdl_include "strain_engine.va"\n' if simulator == "spectre" else ""

    return dedent(
        f"""
        {ahdl}.subckt strain_aware_device d g s b eps_s alpha
        .param nu={strain.nu} beta={strain.beta} gamma={strain.gamma} vth0={strain.vth0} mu0={strain.mu0}
        .param beta_r={config.dynamic.beta_r} gamma_r={config.dynamic.gamma_r} tau_m={_mechanical_tau(config.dynamic)}
        .param tau_load={_hysteresis_taus(config.dynamic)[0]} tau_unload={_hysteresis_taus(config.dynamic)[1]}
        {engine}
        E_gshift g_eff g dvth 0 -1
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


def _strain_source_lines(profile: StrainProfileConfig) -> tuple[str, str]:
    """Return SPICE source declarations for applied strain and angle."""
    profile_type = profile.type.lower()
    if profile_type == "sine":
        eps_source = (
            f"Veps eps_s 0 SIN({profile.offset} {profile.amplitude} "
            f"{profile.frequency} 0 0 0)"
        )
    elif profile_type == "pwl":
        half_period = 0.5 / max(profile.frequency, 1e-6)
        peak = profile.offset + profile.amplitude
        eps_source = (
            f"Veps eps_s 0 PWL(0 {profile.offset} "
            f"{half_period:.6g} {peak:.6g} "
            f"{2 * half_period:.6g} {profile.offset})"
        )
    else:
        eps_source = f"Veps eps_s 0 dc {profile.offset}"

    if profile.alpha_rate != 0.0:
        alpha_source = (
            f"Balpha alpha 0 V = '{{ {profile.alpha} + {profile.alpha_rate} * time }}'"
        )
    else:
        alpha_source = f"Valp alpha 0 dc {profile.alpha}"

    return eps_source, alpha_source


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
    eps_source, alpha_source = _strain_source_lines(profile)
    print_vars = ["time", "v(eps_s)", "v(alpha)", "i(Vdd)"]

    if wrapped:
        return dedent(
            f"""
            {header}
            * {title}
            {includes}
            {eps_source}
            {alpha_source}
            {bias}
            {instance_line}
            .tran {tstep} {tstop}
            .print tran {' '.join(print_vars)}
            .end
            """
        ).strip() + "\n"

    return dedent(
        f"""
        {header}
        * {title}
        {includes}
        {eps_source}
        {alpha_source}
        {bias}
        {mobility_bias}
        {instance_line}
        .tran {tstep} {tstop}
        .print tran {' '.join(print_vars)}
        .end
        """
    ).strip() + "\n"


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

    return dedent(
        f"""
        {header}
        * {title}
        {includes}

        {sweep_decl}
        {fixed}
        {bias}
        {mobility_bias}

        {instance_line}

        .dc {sweep_source} {sweep_start} {sweep_stop} {sweep_step}
        .print dc {' '.join(print_vars)}
        .end
        """
    ).strip() + "\n"


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
        return dedent(
            f"""
            {header}
            * {title}
            {includes}
            Veps eps_s 0 dc {eps_s}
            Valp alpha 0 dc {alpha}
            {bias}
            {instance_line}
            .dc Vgs {vgs_min} {vgs_max} {vgs_step}
            .print dc v(eps_s) v(g) i(Vdd)
            .end
            """
        ).strip() + "\n"

    return dedent(
        f"""
        {header}
        * {title}
        {includes}
        {bias}
        {mobility_bias}
        {instance_line}
        .dc Vgs {vgs_min} {vgs_max} {vgs_step}
        .print dc v(g) i(Vdd)
        .end
        """
    ).strip() + "\n"


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

    device_copy = output_dir / device_source_path.name
    device_copy.write_text(device.body + "\n", encoding="utf-8")

    wrapper_path = output_dir / "strain_wrap.inc"
    wrapper_parts: list[str] = [device.body, _wrapper_subckt(device, config, simulator)]
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

    baseline_transient_tb = None
    strained_transient_tb = None
    if config.transient.enabled:
        baseline_transient_tb = output_dir / f"tb_baseline_transient{suffix}"
        strained_transient_tb = output_dir / f"tb_strained_transient{suffix}"
        baseline_transient_tb.write_text(
            _transient_testbench(
                simulator=simulator,
                include_files=[device_copy.name],
                instance_line=_baseline_instance(device, config),
                bias=bias,
                mobility_bias=mobility_bias,
                profile=config.transient.profile,
                tstop=config.transient.tstop,
                tstep=config.transient.tstep,
                title="baseline transient strain profile",
                wrapped=False,
            ),
            encoding="utf-8",
        )
        strained_transient_tb.write_text(
            _transient_testbench(
                simulator=simulator,
                include_files=["strain_wrap.inc"],
                instance_line=_strained_instance(config),
                bias=bias,
                mobility_bias="",
                profile=config.transient.profile,
                tstop=config.transient.tstop,
                tstep=config.transient.tstep,
                title="strained transient strain profile",
                wrapped=True,
            ),
            encoding="utf-8",
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
        baseline_transient_tb=baseline_transient_tb,
        strained_transient_tb=strained_transient_tb,
    )
