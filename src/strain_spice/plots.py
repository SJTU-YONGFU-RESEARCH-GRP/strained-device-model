"""Matplotlib helpers for strain comparison figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from strain_spice.config import StrainSpiceConfig
from strain_spice.simulator import SimulationResult, find_column
from strain_spice.strain_math import strain_parameter_shifts

FIGSIZE = (11.0, 5.0)
LINE_COLORS = ("#0033cc", "#cc0000", "#7f3fbf", "#e67300")
LINEWIDTH = 3.0


def _apply_style(ax: plt.Axes) -> None:
    """Apply publication-style axis formatting."""
    ax.grid(alpha=0.35, linewidth=1.1)
    ax.tick_params(axis="both", labelsize=10)
    for spine in ax.spines.values():
        spine.set_linewidth(2.0)
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)


def _save_figure(fig: plt.Figure, path: Path) -> None:
    """Save a figure to disk."""
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)


def plot_magnitude_comparison(
    baseline: SimulationResult,
    strained: SimulationResult,
    output_path: Path,
) -> None:
    """Plot drain current versus applied strain."""
    eps_b = find_column(baseline, ("v(eps_s)",))
    id_b = np.abs(find_column(baseline, ("i(vdd)", "vdd#branch")))
    eps_s = find_column(strained, ("v(eps_s)",))
    id_s = np.abs(find_column(strained, ("i(vdd)", "vdd#branch")))

    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.plot(eps_b * 100.0, id_b * 1e3, color=LINE_COLORS[0], linewidth=LINEWIDTH, label="No strain wrapper")
    ax.plot(eps_s * 100.0, id_s * 1e3, color=LINE_COLORS[1], linewidth=LINEWIDTH, label="Strain-aware wrapper")
    ax.set_xlabel("Applied strain ε_S [%]")
    ax.set_ylabel("|I_D| [mA]")
    ax.set_title("Drain current vs applied strain", fontsize=17, fontweight="bold")
    ax.legend()
    _apply_style(ax)
    _save_figure(fig, output_path)


def plot_direction_comparison(
    baseline: SimulationResult,
    strained: SimulationResult,
    output_path: Path,
) -> None:
    """Plot drain current versus force direction."""
    alpha_b = find_column(baseline, ("v(alpha)",))
    id_b = np.abs(find_column(baseline, ("i(vdd)", "vdd#branch")))
    alpha_s = find_column(strained, ("v(alpha)",))
    id_s = np.abs(find_column(strained, ("i(vdd)", "vdd#branch")))

    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.plot(np.degrees(alpha_b), id_b * 1e3, color=LINE_COLORS[0], linewidth=LINEWIDTH, label="No strain wrapper")
    ax.plot(np.degrees(alpha_s), id_s * 1e3, color=LINE_COLORS[1], linewidth=LINEWIDTH, label="Strain-aware wrapper")
    ax.set_xlabel("Force angle α [deg]")
    ax.set_ylabel("|I_D| [mA]")
    ax.set_title("Drain current vs force direction", fontsize=17, fontweight="bold")
    ax.legend()
    _apply_style(ax)
    _save_figure(fig, output_path)


def plot_transfer_comparison(
    baseline_cases: list[SimulationResult],
    strained_cases: list[SimulationResult],
    eps_s_cases: list[float],
    output_path: Path,
) -> None:
    """Plot Id-Vgs transfer curves for multiple strain levels."""
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for index, (baseline, strained, eps_s) in enumerate(
        zip(baseline_cases, strained_cases, eps_s_cases, strict=True)
    ):
        vgs_b = find_column(baseline, ("v(g)",))
        id_b = np.abs(find_column(baseline, ("i(vdd)", "vdd#branch")))
        vgs_s = find_column(strained, ("v(g)",))
        id_s = np.abs(find_column(strained, ("i(vdd)", "vdd#branch")))
        color = LINE_COLORS[index % len(LINE_COLORS)]
        ax.plot(
            vgs_b,
            id_b * 1e3,
            color=color,
            linewidth=LINEWIDTH,
            linestyle="--",
            label=f"No wrapper (ref), ε_S={eps_s * 100:.2f}%",
        )
        ax.plot(
            vgs_s,
            id_s * 1e3,
            color=color,
            linewidth=LINEWIDTH,
            label=f"Strained, ε_S={eps_s * 100:.2f}%",
        )

    ax.set_xlabel("V_GS [V]")
    ax.set_ylabel("|I_D| [mA]")
    ax.set_title("Transfer characteristics: pre vs post strain", fontsize=17, fontweight="bold")
    ax.legend(fontsize=8)
    _apply_style(ax)
    _save_figure(fig, output_path)


def plot_strain_controls(
    strained: SimulationResult,
    output_path: Path,
    config: StrainSpiceConfig,
) -> None:
    """Plot strain-induced ΔVth and Δμ computed from sweep inputs."""
    eps_s = find_column(strained, ("v(eps_s)",))
    alpha = find_column(strained, ("v(alpha)",))
    dvth, dmu = strain_parameter_shifts(
        eps_s,
        alpha,
        nu=config.strain.nu,
        beta=config.strain.beta,
        gamma=config.strain.gamma,
    )

    fig, ax1 = plt.subplots(figsize=FIGSIZE)
    ax1.plot(eps_s * 100.0, dvth, color=LINE_COLORS[0], linewidth=LINEWIDTH, label="ΔVth")
    ax1.set_xlabel("Applied strain ε_S [%]")
    ax1.set_ylabel("ΔVth [V]", color=LINE_COLORS[0])
    ax1.tick_params(axis="y", labelcolor=LINE_COLORS[0])

    ax2 = ax1.twinx()
    ax2.plot(eps_s * 100.0, dmu, color=LINE_COLORS[1], linewidth=LINEWIDTH, label="Δμ")
    ax2.set_ylabel("Δμ (model units)", color=LINE_COLORS[1])
    ax2.tick_params(axis="y", labelcolor=LINE_COLORS[1])

    ax1.set_title("Strain-induced parameter shifts", fontsize=17, fontweight="bold")
    _apply_style(ax1)
    _save_figure(fig, output_path)
