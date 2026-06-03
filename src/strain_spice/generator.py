"""Generate strain-aware and baseline SPICE netlists."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from strain_spice.config import BiasConfig, StrainSpiceConfig
from strain_spice.parser import SubcktDefinition


STRAIN_ENGINE_SPICE = dedent(
    """
    .subckt strain_engine_spice eps_s alpha dvth dmu
    .param nu=0.47 beta=1.0 gamma=0.05
    Beps_t n_eps_t 0 V = '{ (V(eps_s)/2) * (1 - nu + (1 + nu) * cos(2 * V(alpha))) }'
    Bdvth dvth 0 V = '{ -beta * V(n_eps_t) }'
    Bdmu dmu 0 V = '{ gamma * V(n_eps_t) }'
    .ends strain_engine_spice
    """
).strip()


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


def _format_instance_params(params: dict[str, float | str]) -> str:
    """Format ngspice instance parameter assignments."""
    if not params:
        return ""
    assignments = " ".join(f"{key}={value}" for key, value in params.items())
    return f" {assignments}"


def _wrapper_subckt(device: SubcktDefinition, config: StrainSpiceConfig) -> str:
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

    return dedent(
        f"""
        .subckt strain_aware_device d g s b eps_s alpha
        .param nu={strain.nu} beta={strain.beta} gamma={strain.gamma} vth0={strain.vth0} mu0={strain.mu0}
        Xse eps_s alpha dvth dmu strain_engine_spice nu=nu beta=beta gamma=gamma
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
        f"vth0={strain.vth0} mu0={strain.mu0}"
    )


def _step_size(total: float, steps: int) -> float:
    """Compute a positive sweep step size."""
    if steps <= 1:
        return total if total > 0 else 1.0
    return total / (steps - 1)


def _dc_testbench(
    *,
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
    includes = "\n".join(f".include {name}" for name in include_files)
    fixed = "\n".join(f"{name} {node} 0 dc {value}" for name, node, value in fixed_sources)
    sweep_decl = ""
    if sweep_node not in {node for _, node, _ in fixed_sources}:
        sweep_decl = f"{sweep_source} {sweep_node} 0 dc {sweep_start}"

    print_vars = ["v(eps_s)", "v(alpha)", "i(Vdd)"]

    return dedent(
        f"""
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
    includes = "\n".join(f".include {name}" for name in include_files)
    if wrapped:
        return dedent(
            f"""
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

    device_copy = output_dir / device_source_path.name
    device_copy.write_text(device.body + "\n", encoding="utf-8")

    wrapper_path = output_dir / "strain_wrap.inc"
    wrapper_text = "\n\n".join([STRAIN_ENGINE_SPICE, device.body, _wrapper_subckt(device, config)])
    wrapper_path.write_text(wrapper_text + "\n", encoding="utf-8")

    bias = _common_bias(config.bias)
    mobility_port = config.device.mobility_control_port
    mobility_bias = f"Vdmu {mobility_port} 0 dc 0" if mobility_port is not None else ""

    magnitude = config.sweeps.strain_magnitude
    direction = config.sweeps.strain_direction
    transfer = config.sweeps.transfer

    baseline_magnitude = output_dir / "tb_baseline_magnitude.cir"
    strained_magnitude = output_dir / "tb_strained_magnitude.cir"
    baseline_direction = output_dir / "tb_baseline_direction.cir"
    strained_direction = output_dir / "tb_strained_direction.cir"

    baseline_magnitude.write_text(
        _dc_testbench(
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
            baseline_path = output_dir / f"tb_baseline_transfer_{index}.cir"
            strained_path = output_dir / f"tb_strained_transfer_{index}.cir"
            baseline_path.write_text(
                _transfer_testbench(
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
    )
