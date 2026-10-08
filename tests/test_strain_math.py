"""Tests for dynamic strain equations."""

from __future__ import annotations

import numpy as np

from strain_spice.strain_math import (
    apply_hysteresis,
    apply_mechanical_filter,
    channel_strain,
    dynamic_strain_response,
    strain_parameter_shifts,
)


def test_channel_strain_matches_alpha_extrema() -> None:
    """Channel strain should peak at alpha=0 and be negative at alpha=pi/2."""
    nu = 0.47
    eps_s = np.array([0.005])
    eps_parallel = channel_strain(eps_s, np.array([0.0]), nu)[0]
    eps_perp = channel_strain(eps_s, np.array([np.pi / 2.0]), nu)[0]
    assert eps_parallel > 0.0
    assert eps_perp < 0.0


def test_mechanical_filter_lags_step_input() -> None:
    """Filtered strain should lag a step change in applied strain."""
    time_s = np.linspace(0.0, 0.5, 51)
    eps_s = np.where(time_s >= 0.1, 0.005, 0.0)
    filtered = apply_mechanical_filter(eps_s, time_s, tau_m=0.05)
    assert filtered[-1] > filtered[10]
    assert filtered[-1] < eps_s[-1]


def test_hysteresis_asymmetric_tracking() -> None:
    """Unload branch should lag behind load branch on a triangle waveform."""
    time_s = np.linspace(0.0, 2.0, 401)
    eps_t_raw = np.where(time_s <= 1.0, time_s * 0.005, (2.0 - time_s) * 0.005)
    tracked = apply_hysteresis(
        eps_t_raw,
        time_s,
        enabled=True,
        tau_load=0.01,
        tau_unload=0.20,
    )
    peak_index = int(np.argmax(tracked))
    assert tracked[peak_index] < eps_t_raw[peak_index]


def test_dynamic_response_includes_rate_term() -> None:
    """Strain-rate sensitivity should change dvth during transients."""
    time_s = np.linspace(0.0, 1.0, 101)
    eps_s = 0.0025 * (1.0 - np.cos(2.0 * np.pi * time_s))
    alpha = np.zeros_like(time_s)
    _, _, _, dvth_static, _ = dynamic_strain_response(
        eps_s,
        alpha,
        time_s,
        nu=0.47,
        beta=0.8,
        gamma=0.0,
        beta_r=0.0,
    )
    _, _, _, dvth_dynamic, _ = dynamic_strain_response(
        eps_s,
        alpha,
        time_s,
        nu=0.47,
        beta=0.8,
        gamma=0.0,
        beta_r=2.0,
    )
    assert np.max(np.abs(dvth_dynamic - dvth_static)) > 0.0


def test_static_parameter_shifts_match_sign_convention() -> None:
    """Tensile channel strain should reduce threshold in the Liu convention."""
    eps_s = np.array([0.005])
    alpha = np.array([0.0])
    dvth, _ = strain_parameter_shifts(
        eps_s,
        alpha,
        nu=0.47,
        beta=0.8,
        gamma=0.0,
    )
    assert dvth[0] < 0.0
