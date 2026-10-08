"""Markdown report generation for strain comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from strain_spice.config import StrainProfileConfig, StrainSpiceConfig
from strain_spice.simulator import SimulationResult, find_column
from strain_spice.strain_profiles import describe_profile


@dataclass(frozen=True)
class TransientCaseResult:
    """Paired baseline/strained transient simulations for one strain profile."""

    slug: str
    profile: StrainProfileConfig
    baseline: SimulationResult
    strained: SimulationResult

    @property
    def metrics(self) -> TransientMetrics:
        """Compute summary metrics for this transient case."""
        return _transient_metrics(self.baseline, self.strained)


@dataclass(frozen=True)
class ComparisonMetrics:
    """Summary metrics for a paired simulation."""

    name: str
    baseline_id: float
    strained_id: float
    relative_change_pct: float


@dataclass(frozen=True)
class TransientMetrics:
    """Time-domain drain-current metrics for a transient strain profile."""

    peak_baseline: float
    peak_strained: float
    peak_relative_change_pct: float
    rms_baseline: float
    rms_strained: float
    rms_relative_change_pct: float
    ptp_baseline: float
    ptp_strained: float
    ptp_relative_change_pct: float
    phase_lag_s: float


def _format_metric_value(value: float) -> str:
    """Format a numeric metric for markdown tables."""
    if not np.isfinite(value):
        return "—"
    return f"{value:.6g}"


def _format_relative_change(value: float) -> str:
    """Format a relative percent change for markdown tables."""
    if not np.isfinite(value):
        return "—"
    return f"{value:.3f}"


def _sanitize_table_cell(value: str) -> str:
    """Escape characters that would break markdown table rendering."""
    return value.replace("|", "&#124;")


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a markdown table."""
    safe_headers = [_sanitize_table_cell(header) for header in headers]
    header_line = "| " + " | ".join(safe_headers) + " |"
    separator = "| " + " | ".join(["---"] * len(safe_headers)) + " |"
    body = "\n".join(
        "| " + " | ".join(_sanitize_table_cell(cell) for cell in row) + " |" for row in rows
    )
    return "\n".join([header_line, separator, body])


def _relative_change_pct(baseline: float, strained: float) -> float:
    """Compute percent change from baseline to strained."""
    if baseline == 0.0:
        return float("inf") if strained != 0.0 else 0.0
    return (strained - baseline) / baseline * 100.0


def _phase_lag_seconds(time_s: np.ndarray, reference: np.ndarray, response: np.ndarray) -> float:
    """Estimate lag of ``response`` behind ``reference`` via cross-correlation."""
    if len(time_s) < 2:
        return 0.0

    ref = reference - float(np.mean(reference))
    resp = response - float(np.mean(response))
    ref_std = float(np.std(ref))
    resp_std = float(np.std(resp))
    if ref_std < 1e-15 or resp_std < 1e-15:
        return 0.0

    ref_norm = ref / ref_std
    resp_norm = resp / resp_std
    correlation = np.correlate(resp_norm, ref_norm, mode="full")
    lag_index = int(np.argmax(correlation)) - (len(ref_norm) - 1)
    dt = float(np.median(np.diff(time_s)))
    return lag_index * dt


def _transient_metrics(
    baseline: SimulationResult,
    strained: SimulationResult,
) -> TransientMetrics:
    """Compute peak, RMS, peak-to-peak, and phase-lag metrics for transient runs."""
    time_s = find_column(strained, ("time",))
    eps_s = find_column(strained, ("v(eps_s)",))
    id_base = np.abs(find_column(baseline, ("i(vdd)",)))
    id_strained = np.abs(find_column(strained, ("i(vdd)",)))

    peak_base = float(np.max(id_base))
    peak_strained = float(np.max(id_strained))
    rms_base = float(np.sqrt(np.mean(id_base**2)))
    rms_strained = float(np.sqrt(np.mean(id_strained**2)))
    ptp_base = float(np.max(id_base) - np.min(id_base))
    ptp_strained = float(np.max(id_strained) - np.min(id_strained))

    return TransientMetrics(
        peak_baseline=peak_base,
        peak_strained=peak_strained,
        peak_relative_change_pct=_relative_change_pct(peak_base, peak_strained),
        rms_baseline=rms_base,
        rms_strained=rms_strained,
        rms_relative_change_pct=_relative_change_pct(rms_base, rms_strained),
        ptp_baseline=ptp_base,
        ptp_strained=ptp_strained,
        ptp_relative_change_pct=_relative_change_pct(ptp_base, ptp_strained),
        phase_lag_s=_phase_lag_seconds(time_s, eps_s, id_strained),
    )


def _peak_relative_change(baseline: SimulationResult, strained: SimulationResult) -> ComparisonMetrics:
    """Compute relative drain-current change at maximum sweep point."""
    id_b = np.abs(find_column(baseline, ("i(vdd)",)))
    id_s = np.abs(find_column(strained, ("i(vdd)",)))
    index = int(np.argmax(strained.columns.get("v(eps_s)", id_s)))
    base = float(id_b[min(index, len(id_b) - 1)])
    strained_value = float(id_s[index])
    if base == 0.0:
        relative = float("inf") if strained_value != 0.0 else 0.0
    else:
        relative = (strained_value - base) / base * 100.0
    return ComparisonMetrics(
        name=strained.name,
        baseline_id=base,
        strained_id=strained_value,
        relative_change_pct=relative,
    )


def _sample_rows(result: SimulationResult, limit: int = 8) -> list[list[str]]:
    """Return a compact markdown table sample from a simulation result."""
    headers = list(result.columns.keys())
    count = result.row_count
    if count <= limit:
        indices = range(count)
    else:
        indices = np.linspace(0, count - 1, limit, dtype=int)

    rows: list[list[str]] = []
    for index in indices:
        rows.append([f"{result.columns[header][index]:.6g}" for header in headers])
    return rows


def write_report(
    *,
    config: StrainSpiceConfig,
    device_path: Path,
    output_dir: Path,
    magnitude_baseline: SimulationResult,
    magnitude_strained: SimulationResult,
    direction_baseline: SimulationResult,
    direction_strained: SimulationResult,
    transfer_baseline: list[SimulationResult] | None,
    transfer_strained: list[SimulationResult] | None,
    transient_cases: list[TransientCaseResult] | None = None,
    figure_paths: dict[str, Path],
) -> Path:
    """Write a markdown report comparing pre and post strain effects."""
    report_path = output_dir / "strain_comparison_report.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    magnitude_metric = _peak_relative_change(magnitude_baseline, magnitude_strained)
    direction_metric = ComparisonMetrics(
        name="direction",
        baseline_id=float(np.mean(np.abs(find_column(direction_baseline, ("i(vdd)",))))),
        strained_id=float(np.mean(np.abs(find_column(direction_strained, ("i(vdd)",))))),
        relative_change_pct=float(
            (
                np.mean(np.abs(find_column(direction_strained, ("i(vdd)",))))
                - np.mean(np.abs(find_column(direction_baseline, ("i(vdd)",))))
            )
            / max(np.mean(np.abs(find_column(direction_baseline, ("i(vdd)",)))), 1e-15)
            * 100.0
        ),
    )

    lines = [
        f"# {config.title}",
        "",
        f"Generated: {timestamp}",
        "",
        "## Overview",
        "",
        "This report compares simulations **without** the strain wrapper (baseline device only)",
        "and **with** the generated strain-aware wrapper subcircuit.",
        "",
        f"- Device netlist: `{device_path}`",
        f"- Wrapper output directory: `{output_dir}`",
        "",
        "## Strain model parameters",
        "",
        _format_table(
            ["Parameter", "Value", "Description"],
            [
                ["ν", f"{config.strain.nu}", "Substrate Poisson's ratio"],
                ["β", f"{config.strain.beta}", "Threshold voltage sensitivity"],
                ["γ", f"{config.strain.gamma}", "Mobility sensitivity"],
                ["Vth0", f"{config.strain.vth0}", "Unstrained threshold reference"],
                ["μ0", f"{config.strain.mu0}", "Unstrained mobility reference"],
            ],
        ),
        "",
        "## Dynamic device model parameters",
        "",
        _format_table(
            ["Parameter", "Value", "Description"],
            [
                ["τ_m", f"{config.dynamic.mechanical_tau}", "Mechanical low-pass time constant [s] (Option 2)"],
                ["β_r", f"{config.dynamic.beta_r}", "Threshold strain-rate sensitivity (Option 3)"],
                ["γ_r", f"{config.dynamic.gamma_r}", "Mobility strain-rate sensitivity (Option 3)"],
                [
                    "Hysteresis",
                    "enabled" if config.dynamic.hysteresis.enabled else "disabled",
                    "Asymmetric load/unload tracking (Option 4)",
                ],
                ["τ_load", f"{config.dynamic.hysteresis.tau_load}", "Channel-strain loading time constant [s]"],
                ["τ_unload", f"{config.dynamic.hysteresis.tau_unload}", "Channel-strain unloading time constant [s]"],
            ],
        ),
        "",
        "## Summary metrics",
        "",
        _format_table(
            ["Case", "Baseline |I_D| [A]", "Strained |I_D| [A]", "Relative change [%]"],
            [
                [
                    "Strain magnitude sweep",
                    f"{magnitude_metric.baseline_id:.6g}",
                    f"{magnitude_metric.strained_id:.6g}",
                    f"{magnitude_metric.relative_change_pct:.3f}",
                ],
                [
                    "Strain direction sweep (mean)",
                    f"{direction_metric.baseline_id:.6g}",
                    f"{direction_metric.strained_id:.6g}",
                    f"{direction_metric.relative_change_pct:.3f}",
                ],
            ],
        ),
        "",
    ]

    if transient_cases:
        if len(transient_cases) > 1:
            lines.extend(
                [
                    "## Transient profile comparison",
                    "",
                    _format_table(
                        [
                            "Profile",
                            "Peak Δ [%]",
                            "RMS Δ [%]",
                            "Peak-to-peak Δ [%]",
                            "Phase lag [ms]",
                        ],
                        [
                            [
                                case.slug,
                                _format_relative_change(case.metrics.peak_relative_change_pct),
                                _format_relative_change(case.metrics.rms_relative_change_pct),
                                _format_relative_change(case.metrics.ptp_relative_change_pct),
                                f"{case.metrics.phase_lag_s * 1e3:.3f}",
                            ]
                            for case in transient_cases
                        ],
                    ),
                    "",
                ]
            )

        for case in transient_cases:
            transient_metric = case.metrics
            section_title = (
                f"## Transient summary metrics ({case.slug})"
                if len(transient_cases) > 1
                else "## Transient summary metrics"
            )
            lines.extend(
                [
                    section_title,
                    "",
                    _format_table(
                        ["Metric", "Baseline |I_D| [A]", "Strained |I_D| [A]", "Relative change [%]"],
                        [
                            [
                                "Peak",
                                _format_metric_value(transient_metric.peak_baseline),
                                _format_metric_value(transient_metric.peak_strained),
                                _format_relative_change(transient_metric.peak_relative_change_pct),
                            ],
                            [
                                "RMS",
                                _format_metric_value(transient_metric.rms_baseline),
                                _format_metric_value(transient_metric.rms_strained),
                                _format_relative_change(transient_metric.rms_relative_change_pct),
                            ],
                            [
                                "Peak-to-peak",
                                _format_metric_value(transient_metric.ptp_baseline),
                                _format_metric_value(transient_metric.ptp_strained),
                                _format_relative_change(transient_metric.ptp_relative_change_pct),
                            ],
                        ],
                    ),
                    "",
                    f"Phase lag of |I_D| behind applied ε_S (strained case, `{case.slug}`): "
                    f"**{transient_metric.phase_lag_s * 1e3:.3f} ms** "
                    f"({transient_metric.phase_lag_s:.6g} s), estimated by cross-correlation.",
                    "",
                ]
            )

    lines.extend(
        [
            "## Figures",
            "",
        ]
    )

    for title, figure_path in figure_paths.items():
        rel = figure_path.relative_to(output_dir)
        lines.extend([f"### {title}", "", f"![{title}]({rel.as_posix()})", ""])

    lines.extend(
        [
            "## Strain magnitude sweep data (sample)",
            "",
            _format_table(
                list(magnitude_strained.columns.keys()),
                _sample_rows(magnitude_strained),
            ),
            "",
            "## Strain direction sweep data (sample)",
            "",
            _format_table(
                list(direction_strained.columns.keys()),
                _sample_rows(direction_strained),
            ),
            "",
        ]
    )

    if transfer_baseline and transfer_strained:
        lines.extend(["## Transfer sweep notes", ""])
        for index, eps_s in enumerate(config.sweeps.transfer.eps_s_cases):
            base = transfer_baseline[index]
            strained = transfer_strained[index]
            id_base = float(np.max(np.abs(find_column(base, ("i(vdd)",)))))
            id_strained = float(np.max(np.abs(find_column(strained, ("i(vdd)",)))))
            delta = (id_strained - id_base) / max(id_base, 1e-15) * 100.0
            lines.append(
                f"- ε_S = {eps_s * 100:.3f}%: peak |I_D| baseline = {id_base:.6g} A, "
                f"strained = {id_strained:.6g} A, Δ = {delta:.2f}%"
            )
        lines.append("")

    if transient_cases:
        for case in transient_cases:
            slug_suffix = f" ({case.slug})" if len(transient_cases) > 1 else ""
            csv_suffix = f"_{case.slug}" if len(transient_cases) > 1 else ""
            lines.extend(
                [
                    f"## Transient time series (sample){slug_suffix}",
                    "",
                    _format_table(
                        list(case.strained.columns.keys()),
                        _sample_rows(case.strained),
                    ),
                    "",
                    f"## Transient strain profile notes{slug_suffix}",
                    "",
                    f"- Profile: `{case.profile.type}` — "
                    f"{describe_profile(case.profile, tstop=config.transient.tstop)}",
                    f"- Simulation window: 0 to {config.transient.tstop:.3g} s "
                    f"(step = {config.transient.tstep:.3g} s)",
                    f"- Full transient CSV: `tb_strained_transient{csv_suffix}.csv`, "
                    f"`tb_baseline_transient{csv_suffix}.csv`",
                    "",
                ]
            )

    lines.extend(
        [
            "## How to reproduce",
            "",
            "```bash",
            f"strain-spice run --device {device_path} --config <your-config.yaml> --output {output_dir}",
            "```",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_results_index(results_dir: Path) -> Path:
    """Write or update the top-level results index markdown file."""
    index_path = results_dir / "README.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    static_intro = [
        "# Strain-SPICE evaluation results",
        "",
        "Generated simulation outputs from bundled and custom `strain-spice run` jobs.",
        "Re-run `./scripts/run_all.sh` to refresh every bundled evaluation and this index.",
        "",
        "## How to read time-varying results",
        "",
        "Dynamic configs (`transient.enabled: true`) add transient testbenches and figures.",
        "Use `transient.run_all_presets: true` to exercise the built-in profile library "
        "(sine, drift, abrupt, pulse, triangle PWL, custom PWL) in one run.",
        "",
        "- `figures/transient_comparison[_<profile>].svg` — applied strain ε_S(t) and drain current |I_D|(t)",
        "- `figures/transient_controls[_<profile>].svg` — ΔVth and Δμ versus time",
        "- `strain_comparison_report.md` — per-profile metrics plus a comparison table when multiple profiles run",
        "",
        f"Index last updated: {timestamp}",
        "",
        "## Evaluations",
        "",
    ]

    evaluation_lines: list[str] = []
    if results_dir.is_dir():
        for child in sorted(results_dir.iterdir()):
            if not child.is_dir():
                continue
            report_path = child / "strain_comparison_report.md"
            if not report_path.is_file():
                continue

            name = child.name
            evaluation_lines.append(
                f"- **[{name}]({name}/strain_comparison_report.md)**"
            )
            figures_dir = child / "figures"
            transient_figures = sorted(figures_dir.glob("transient_comparison*.svg"))
            if transient_figures:
                for figure_path in transient_figures:
                    slug = figure_path.stem.removeprefix("transient_comparison")
                    slug_label = slug.removeprefix("_") or "default"
                    controls_name = (
                        f"transient_controls{slug}.svg"
                        if slug
                        else "transient_controls.svg"
                    )
                    csv_name = (
                        f"tb_strained_transient{slug}.csv"
                        if slug
                        else "tb_strained_transient.csv"
                    )
                    evaluation_lines.append(
                        f"  - Time-varying ({slug_label}): "
                        f"[|I_D|(t)]({name}/figures/{figure_path.name}), "
                        f"[ΔVth/Δμ(t)]({name}/figures/{controls_name}), "
                        f"[transient CSV]({name}/{csv_name})"
                    )
            elif (figures_dir / "transient_comparison.svg").is_file():
                evaluation_lines.append(
                    f"  - Time-varying: "
                    f"[|I_D|(t)]({name}/figures/transient_comparison.svg), "
                    f"[ΔVth/Δμ(t)]({name}/figures/transient_controls.svg), "
                    f"[transient CSV]({name}/tb_strained_transient.csv)"
                )
            if (figures_dir / "magnitude_comparison.svg").is_file():
                evaluation_lines.append(
                    f"  - DC sweeps: "
                    f"[magnitude]({name}/figures/magnitude_comparison.svg), "
                    f"[direction]({name}/figures/direction_comparison.svg)"
                )

    if not evaluation_lines:
        evaluation_lines.append(
            "_No completed evaluations yet. Run `./scripts/run_all.sh` or a single "
            "`strain-spice run --output results/<name>` job._"
        )

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(static_intro + evaluation_lines + [""]), encoding="utf-8")
    return index_path
