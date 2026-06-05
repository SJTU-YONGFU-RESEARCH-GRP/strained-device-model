"""End-to-end strain wrapper generation, simulation, and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from strain_spice.config import StrainSpiceConfig
from strain_spice.generator import GeneratedNetlists, generate_netlists
from strain_spice.parser import load_device_netlist, parse_subckt
from strain_spice.plots import (
    plot_direction_comparison,
    plot_magnitude_comparison,
    plot_strain_controls,
    plot_transfer_comparison,
    plot_transient_comparison,
)
from strain_spice.report import TransientCaseResult, write_report
from strain_spice.simulator import (
    SimulationResult,
    create_runner,
    parse_print_table,
    save_csv,
)


@dataclass(frozen=True)
class PipelineResult:
    """Artifacts produced by the full workflow."""

    output_dir: Path
    netlists: GeneratedNetlists
    report_path: Path
    figure_paths: dict[str, Path]


def run_pipeline(
    device_path: Path,
    config: StrainSpiceConfig,
    output_dir: Path,
) -> PipelineResult:
    """Generate netlists, simulate, plot, and write a markdown report."""
    device_source = load_device_netlist(device_path)
    device = parse_subckt(device_source, config.device.subckt)

    if config.device.subckt is None:
        config.device.subckt = device.name

    netlists = generate_netlists(device, device_path, config, output_dir)
    runner = create_runner(config)
    workdir = netlists.output_dir

    def simulate(path: Path, name: str, analysis: str = "dc") -> SimulationResult:
        output = runner.run(path, workdir=workdir)
        result = parse_print_table(output, name=name, analysis=analysis)
        save_csv(result, path.with_suffix(".csv"))
        return result

    magnitude_baseline = simulate(netlists.baseline_magnitude_tb, "baseline_magnitude")
    magnitude_strained = simulate(netlists.strained_magnitude_tb, "strained_magnitude")
    direction_baseline = simulate(netlists.baseline_direction_tb, "baseline_direction")
    direction_strained = simulate(netlists.strained_direction_tb, "strained_direction")

    transfer_baseline = None
    transfer_strained = None
    if netlists.baseline_transfer_tbs:
        transfer_baseline = [
            simulate(path, f"baseline_transfer_{index}")
            for index, path in enumerate(netlists.baseline_transfer_tbs)
        ]
        transfer_strained = [
            simulate(path, f"strained_transfer_{index}")
            for index, path in enumerate(netlists.strained_transfer_tbs)
        ]

    transient_case_results: list[TransientCaseResult] = []
    for case in netlists.transient_cases:
        baseline = simulate(case.baseline_tb, f"baseline_transient_{case.slug}", analysis="tran")
        strained = simulate(case.strained_tb, f"strained_transient_{case.slug}", analysis="tran")
        transient_case_results.append(
            TransientCaseResult(
                slug=case.slug,
                profile=case.profile,
                baseline=baseline,
                strained=strained,
            )
        )

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    figure_paths = {
        "Drain current vs applied strain": figures_dir / "magnitude_comparison.svg",
        "Drain current vs force direction": figures_dir / "direction_comparison.svg",
        "Strain-induced parameter shifts": figures_dir / "strain_controls.svg",
    }

    plot_magnitude_comparison(magnitude_baseline, magnitude_strained, figure_paths["Drain current vs applied strain"])
    plot_direction_comparison(direction_baseline, direction_strained, figure_paths["Drain current vs force direction"])
    plot_strain_controls(magnitude_strained, figure_paths["Strain-induced parameter shifts"], config)

    if transfer_baseline and transfer_strained:
        transfer_figure = figures_dir / "transfer_comparison.svg"
        plot_transfer_comparison(
            transfer_baseline,
            transfer_strained,
            config.sweeps.transfer.eps_s_cases,
            transfer_figure,
        )
        figure_paths["Transfer characteristics"] = transfer_figure

    for case_result in transient_case_results:
        slug_suffix = f"_{case_result.slug}" if len(transient_case_results) > 1 else ""
        transient_figure = figures_dir / f"transient_comparison{slug_suffix}.svg"
        controls_figure = figures_dir / f"transient_controls{slug_suffix}.svg"
        plot_transient_comparison(case_result.baseline, case_result.strained, transient_figure)
        plot_strain_controls(case_result.strained, controls_figure, config)
        title_prefix = f"Dynamic transient response ({case_result.slug})"
        figure_paths[title_prefix] = transient_figure
        figure_paths[f"Dynamic parameter shifts ({case_result.slug})"] = controls_figure

    report_path = write_report(
        config=config,
        device_path=device_path,
        output_dir=output_dir,
        magnitude_baseline=magnitude_baseline,
        magnitude_strained=magnitude_strained,
        direction_baseline=direction_baseline,
        direction_strained=direction_strained,
        transfer_baseline=transfer_baseline,
        transfer_strained=transfer_strained,
        transient_cases=transient_case_results,
        figure_paths=figure_paths,
    )

    return PipelineResult(
        output_dir=output_dir,
        netlists=netlists,
        report_path=report_path,
        figure_paths=figure_paths,
    )
