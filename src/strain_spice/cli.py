"""Command-line interface for strain SPICE workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from strain_spice.config import StrainSpiceConfig
from strain_spice.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Wrap a user SPICE device model with strain effects, simulate, and report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate wrapper, simulate, and write report.")
    run_parser.add_argument(
        "--device",
        type=Path,
        required=True,
        help="Path to the user device .subckt netlist.",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="YAML configuration file.",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        default=Path("results"),
        help="Output directory for generated netlists, CSV, figures, and markdown.",
    )
    run_parser.add_argument(
        "--simulator",
        choices=["ngspice", "spectre"],
        default=None,
        help="Circuit simulator backend (overrides config simulator field).",
    )

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        config = StrainSpiceConfig.from_yaml(args.config)
        if args.simulator is not None:
            config.simulator = args.simulator
        result = run_pipeline(args.device, config, args.output)
        print(f"Generated wrapper: {result.netlists.wrapper}")
        print(f"Report: {result.report_path}")
        for title, path in result.figure_paths.items():
            print(f"Figure ({title}): {path}")


if __name__ == "__main__":
    main()
