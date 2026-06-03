"""Strain equation helpers."""

from __future__ import annotations

import numpy as np


def channel_strain(eps_s: np.ndarray, alpha: np.ndarray, nu: float) -> np.ndarray:
    """Compute effective channel strain from applied strain and angle."""
    return (eps_s / 2.0) * (1.0 - nu + (1.0 + nu) * np.cos(2.0 * alpha))


def strain_parameter_shifts(
    eps_s: np.ndarray,
    alpha: np.ndarray,
    *,
    nu: float,
    beta: float,
    gamma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ΔVth and Δμ arrays for the given strain inputs."""
    eps_t = channel_strain(eps_s, alpha, nu)
    return -beta * eps_t, gamma * eps_t
