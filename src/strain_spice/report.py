"""Markdown report generation for strain comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from strain_spice.config import StrainSpiceConfig
from strain_spice.simulator import SimulationResult, find_column


@dataclass(frozen=True)
class ComparisonMetrics:
    """Summary metrics for a paired simulation."""

    name: str
    baseline_id: float
    strained_id: float
    relative_change_pct: float


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a markdown table."""
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join([header_line, separator, body])


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
        "## Figures",
        "",
    ]

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
