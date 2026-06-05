"""Tests for built-in transient strain profile presets."""

from __future__ import annotations

import pytest

from strain_spice.config import StrainProfileConfig, TransientConfig
from strain_spice.strain_profiles import (
    BUILTIN_PROFILE_TYPES,
    builtin_preset_profiles,
    describe_profile,
    resolve_transient_profiles,
    strain_eps_source,
    strain_source_lines,
)


@pytest.mark.parametrize("profile_type", BUILTIN_PROFILE_TYPES)
def test_strain_eps_source_generates_spice_line(profile_type: str) -> None:
    """Each built-in profile type should emit a valid SPICE source line."""
    profile = StrainProfileConfig(
        type=profile_type,
        amplitude=0.005,
        frequency=0.3,
        rate=1e-3,
        t_step=1.0,
        points=[[0.0, 0.0], [1.0, 0.005], [5.0, 0.0]],
    )
    source = strain_eps_source(profile, tstop=5.0)

    assert source.startswith("Veps eps_s 0")
    if profile_type == "sine":
        assert "SIN(" in source
    elif profile_type in {"drift", "abrupt", "pwl", "custom"}:
        assert "PWL(" in source
    elif profile_type == "pulse":
        assert "PULSE(" in source
    elif profile_type == "dc":
        assert "dc" in source


def test_drift_profile_ramps_to_expected_end_value() -> None:
    """Drift profiles should reach offset + rate * tstop at the simulation end."""
    profile = StrainProfileConfig(type="drift", offset=0.001, rate=0.0008)
    source = strain_eps_source(profile, tstop=5.0)

    assert "PWL(0 0.001 5 0.005)" in source


def test_abrupt_profile_steps_at_configured_time() -> None:
    """Abrupt profiles should include a step transition at ``t_step``."""
    profile = StrainProfileConfig(
        type="abrupt",
        offset=0.0,
        t_step=1.0,
        value_after=0.005,
    )
    source = strain_eps_source(profile, tstop=5.0)

    assert "PWL(0 0 1 0 1 0.005 5 0.005)" in source


def test_custom_profile_uses_user_points() -> None:
    """Custom profiles should serialize user-provided PWL points."""
    profile = StrainProfileConfig(
        type="custom",
        points=[[0.0, 0.0], [0.5, 0.003], [2.0, 0.0]],
    )
    source = strain_eps_source(profile, tstop=2.0)

    assert "PWL(0 0 0.5 0.003 2 0)" in source


def test_run_all_presets_resolves_six_builtin_profiles() -> None:
    """Preset mode should expand to the bundled profile library."""
    transient = TransientConfig(
        enabled=True,
        run_all_presets=True,
        profile=StrainProfileConfig(amplitude=0.005, frequency=0.3),
    )
    cases = resolve_transient_profiles(transient)

    assert [case.slug for case in cases] == [
        "sine",
        "drift",
        "abrupt",
        "pulse",
        "pwl",
        "custom",
    ]
    assert len(builtin_preset_profiles(transient.profile, tstop=transient.tstop)) == 6


def test_alpha_rate_uses_behavioral_source() -> None:
    """Non-zero alpha_rate should emit a behavioral angle source."""
    profile = StrainProfileConfig(type="sine", alpha_rate=0.1)
    _, alpha_source = strain_source_lines(profile, tstop=5.0)

    assert "Balpha" in alpha_source
    assert "alpha_rate" not in alpha_source
    assert "0.1 * time" in alpha_source


def test_describe_profile_includes_type_specific_details() -> None:
    """Profile descriptions should be suitable for markdown reports."""
    drift = StrainProfileConfig(type="drift", offset=0.0, rate=0.001)
    abrupt = StrainProfileConfig(type="abrupt", offset=0.0, t_step=1.0, value_after=0.005)

    assert "drift" in describe_profile(drift, tstop=5.0)
    assert "abrupt step" in describe_profile(abrupt, tstop=5.0)
