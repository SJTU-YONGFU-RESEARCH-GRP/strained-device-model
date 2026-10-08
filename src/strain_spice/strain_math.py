"""Strain equation helpers."""

from __future__ import annotations

import numpy as np


def channel_strain(eps_s: np.ndarray, alpha: np.ndarray, nu: float) -> np.ndarray:
    """Compute effective channel strain from applied strain and angle."""
    return (eps_s / 2.0) * (1.0 - nu + (1.0 + nu) * np.cos(2.0 * alpha))


def apply_mechanical_filter(
    eps_s: np.ndarray,
    time_s: np.ndarray,
    *,
    tau_m: float,
) -> np.ndarray:
    """Low-pass filter applied strain to emulate mechanical bandwidth."""
    if tau_m <= 0.0 or eps_s.size == 0:
        return eps_s.copy()

    filtered = np.empty_like(eps_s, dtype=float)
    filtered[0] = eps_s[0]
    for index in range(1, eps_s.size):
        dt = max(float(time_s[index] - time_s[index - 1]), 1e-15)
        alpha_step = dt / (tau_m + dt)
        filtered[index] = filtered[index - 1] + alpha_step * (eps_s[index] - filtered[index - 1])
    return filtered


def apply_hysteresis(
    eps_t_raw: np.ndarray,
    time_s: np.ndarray,
    *,
    enabled: bool,
    tau_load: float,
    tau_unload: float,
) -> np.ndarray:
    """Track channel strain with asymmetric load/unload time constants."""
    if not enabled or eps_t_raw.size == 0:
        return eps_t_raw.copy()

    tau_load = max(tau_load, 1e-15)
    tau_unload = max(tau_unload, 1e-15)
    state = np.empty_like(eps_t_raw, dtype=float)
    state[0] = eps_t_raw[0]
    for index in range(1, eps_t_raw.size):
        dt = max(float(time_s[index] - time_s[index - 1]), 1e-15)
        error = eps_t_raw[index] - state[index - 1]
        tau = tau_load if error >= 0.0 else tau_unload
        alpha_step = dt / (tau + dt)
        state[index] = state[index - 1] + alpha_step * error
    return state


def strain_rate(eps_t: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    """Compute the time derivative of channel strain."""
    if eps_t.size < 2:
        return np.zeros_like(eps_t, dtype=float)
    return np.gradient(eps_t, time_s)


def strain_parameter_shifts(
    eps_s: np.ndarray,
    alpha: np.ndarray,
    *,
    nu: float,
    beta: float,
    gamma: float,
    beta_r: float = 0.0,
    gamma_r: float = 0.0,
    eps_t: np.ndarray | None = None,
    eps_t_dot: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ΔVth and Δμ arrays for the given strain inputs."""
    if eps_t is None:
        eps_t = channel_strain(eps_s, alpha, nu)
    if eps_t_dot is None:
        eps_t_dot = np.zeros_like(eps_t, dtype=float)
    return -beta * eps_t - beta_r * eps_t_dot, gamma * eps_t + gamma_r * eps_t_dot


def dynamic_strain_response(
    eps_s: np.ndarray,
    alpha: np.ndarray,
    time_s: np.ndarray,
    *,
    nu: float,
    beta: float,
    gamma: float,
    mechanical_tau: float = 0.0,
    beta_r: float = 0.0,
    gamma_r: float = 0.0,
    hysteresis_enabled: bool = False,
    hysteresis_tau_load: float = 0.05,
    hysteresis_tau_unload: float = 0.20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute the full dynamic strain-to-parameter chain in Python."""
    eps_s_eff = apply_mechanical_filter(eps_s, time_s, tau_m=mechanical_tau)
    eps_t_raw = channel_strain(eps_s_eff, alpha, nu)
    eps_t = apply_hysteresis(
        eps_t_raw,
        time_s,
        enabled=hysteresis_enabled,
        tau_load=hysteresis_tau_load,
        tau_unload=hysteresis_tau_unload,
    )
    eps_t_dot = strain_rate(eps_t, time_s)
    dvth, dmu = strain_parameter_shifts(
        eps_s_eff,
        alpha,
        nu=nu,
        beta=beta,
        gamma=gamma,
        beta_r=beta_r,
        gamma_r=gamma_r,
        eps_t=eps_t,
        eps_t_dot=eps_t_dot,
    )
    return eps_s_eff, eps_t, eps_t_dot, dvth, dmu
