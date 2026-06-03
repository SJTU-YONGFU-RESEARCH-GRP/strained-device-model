"""Matplotlib helpers for strain comparison figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from strain_spice.config import StrainSpiceConfig
from strain_spice.simulator import SimulationResult, find_column
from strain_spice.strain_math import dynamic_strain_response, strain_parameter_shifts

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
    time_s = strained.columns.get("time")
    if time_s is not None:
        _, _, _, dvth, dmu = dynamic_strain_response(
            eps_s,
            alpha,
            time_s,
            nu=config.strain.nu,
            beta=config.strain.beta,
            gamma=config.strain.gamma,
            mechanical_tau=config.dynamic.mechanical_tau,
            beta_r=config.dynamic.beta_r,
            gamma_r=config.dynamic.gamma_r,
            hysteresis_enabled=config.dynamic.hysteresis.enabled,
            hysteresis_tau_load=config.dynamic.hysteresis.tau_load,
            hysteresis_tau_unload=config.dynamic.hysteresis.tau_unload,
        )
        x_axis = time_s
        x_label = "Time [s]"
    else:
        dvth, dmu = strain_parameter_shifts(
            eps_s,
            alpha,
            nu=config.strain.nu,
            beta=config.strain.beta,
            gamma=config.strain.gamma,
            beta_r=config.dynamic.beta_r,
            gamma_r=config.dynamic.gamma_r,
        )
        x_axis = eps_s * 100.0
        x_label = "Applied strain ε_S [%]"

    fig, ax1 = plt.subplots(figsize=FIGSIZE)
    ax1.plot(x_axis, dvth, color=LINE_COLORS[0], linewidth=LINEWIDTH, label="ΔVth")
    ax1.set_xlabel(x_label)
    ax1.set_ylabel("ΔVth [V]", color=LINE_COLORS[0])
    ax1.tick_params(axis="y", labelcolor=LINE_COLORS[0])

    ax2 = ax1.twinx()
    ax2.plot(x_axis, dmu, color=LINE_COLORS[1], linewidth=LINEWIDTH, label="Δμ")
    ax2.set_ylabel("Δμ (model units)", color=LINE_COLORS[1])
    ax2.tick_params(axis="y", labelcolor=LINE_COLORS[1])

    ax1.set_title("Strain-induced parameter shifts", fontsize=17, fontweight="bold")
    _apply_style(ax1)
    _save_figure(fig, output_path)


def plot_transient_comparison(
    baseline: SimulationResult,
    strained: SimulationResult,
    output_path: Path,
) -> None:
    """Plot drain current versus time for dynamic strain profiles."""
    time_b = find_column(baseline, ("time",))
    id_b = np.abs(find_column(baseline, ("i(vdd)", "vdd#branch")))
    time_s = find_column(strained, ("time",))
    id_s = np.abs(find_column(strained, ("i(vdd)", "vdd#branch")))
    eps_s = find_column(strained, ("v(eps_s)",))

    fig, axes = plt.subplots(2, 1, figsize=(11.0, 8.0), sharex=True)

    axes[0].plot(time_s, eps_s * 100.0, color=LINE_COLORS[2], linewidth=LINEWIDTH)
    axes[0].set_ylabel("Applied strain ε_S [%]")
    axes[0].set_title("Dynamic strain input", fontsize=17, fontweight="bold")
    _apply_style(axes[0])

    axes[1].plot(
        time_b,
        id_b * 1e3,
        color=LINE_COLORS[0],
        linewidth=LINEWIDTH,
        label="No strain wrapper",
    )
    axes[1].plot(
        time_s,
        id_s * 1e3,
        color=LINE_COLORS[1],
        linewidth=LINEWIDTH,
        label="Strain-aware wrapper",
    )
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("|I_D| [mA]")
    axes[1].set_title("Drain current under time-varying strain", fontsize=17, fontweight="bold")
    axes[1].legend()
    _apply_style(axes[1])

    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)
