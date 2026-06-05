"""Built-in time-varying strain profile presets and SPICE source generation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from strain_spice.config import StrainProfileConfig, TransientConfig

BUILTIN_PROFILE_TYPES: tuple[str, ...] = (
    "sine",
    "drift",
    "abrupt",
    "pulse",
    "pwl",
    "custom",
    "dc",
)


@dataclass(frozen=True)
class TransientProfileCase:
    """One resolved transient strain profile with a stable filesystem slug."""

    slug: str
    profile: StrainProfileConfig


def profile_slug(profile: StrainProfileConfig) -> str:
    """Return a stable slug for netlist and figure filenames."""
    if profile.name:
        return profile.name.strip().lower().replace(" ", "_")
    return profile.type.lower()


def _format_pwl_points(pairs: list[tuple[float, float]]) -> str:
    """Format ``(time, value)`` pairs as a SPICE PWL source body."""
    if len(pairs) < 2:
        raise ValueError("PWL strain profiles require at least two (time, value) points")
    tokens = " ".join(f"{time:.6g} {value:.6g}" for time, value in pairs)
    return f"Veps eps_s 0 PWL({tokens})"


def strain_eps_source(profile: StrainProfileConfig, *, tstop: float) -> str:
    """Return the SPICE voltage source line driving applied strain ``eps_s``."""
    profile_type = profile.type.lower()
    offset = profile.offset
    amplitude = profile.amplitude

    if profile_type == "sine":
        return (
            f"Veps eps_s 0 SIN({offset} {amplitude} "
            f"{profile.frequency} 0 0 0)"
        )

    if profile_type == "drift":
        end_value = offset + profile.rate * tstop
        return _format_pwl_points([(0.0, offset), (tstop, end_value)])

    if profile_type == "abrupt":
        value_after = profile.value_after if profile.value_after is not None else offset + amplitude
        t_step = min(max(profile.t_step, 0.0), tstop)
        return _format_pwl_points(
            [
                (0.0, offset),
                (t_step, offset),
                (t_step, value_after),
                (tstop, value_after),
            ]
        )

    if profile_type == "pulse":
        period = 1.0 / max(profile.frequency, 1e-6)
        pulse_width = max(profile.duty, 1e-6) * period
        rise_time = min(max(profile.rise_time, 1e-9), period / 10.0)
        fall_time = min(max(profile.fall_time, 1e-9), period / 10.0)
        peak = offset + amplitude
        return (
            f"Veps eps_s 0 PULSE({offset} {peak} 0 "
            f"{rise_time:.6g} {fall_time:.6g} {pulse_width:.6g} {period:.6g})"
        )

    if profile_type == "pwl":
        half_period = 0.5 / max(profile.frequency, 1e-6)
        peak = offset + amplitude
        return _format_pwl_points(
            [
                (0.0, offset),
                (half_period, peak),
                (2.0 * half_period, offset),
            ]
        )

    if profile_type == "custom":
        pairs = [(float(point[0]), float(point[1])) for point in profile.points]
        return _format_pwl_points(pairs)

    if profile_type == "dc":
        return f"Veps eps_s 0 dc {offset}"

    raise ValueError(
        f"Unsupported strain profile type '{profile.type}'; "
        f"expected one of {BUILTIN_PROFILE_TYPES}"
    )


def alpha_source_line(profile: StrainProfileConfig) -> str:
    """Return the SPICE source line driving force angle ``alpha``."""
    if profile.alpha_rate != 0.0:
        return f"Balpha alpha 0 V = '{{ {profile.alpha} + {profile.alpha_rate} * time }}'"
    return f"Valp alpha 0 dc {profile.alpha}"


def strain_source_lines(profile: StrainProfileConfig, *, tstop: float) -> tuple[str, str]:
    """Return SPICE source declarations for applied strain and force angle."""
    return strain_eps_source(profile, tstop=tstop), alpha_source_line(profile)


def describe_profile(profile: StrainProfileConfig, *, tstop: float) -> str:
    """Return a human-readable summary of a strain profile for reports."""
    profile_type = profile.type.lower()
    if profile_type == "sine":
        return (
            f"sine (offset = {profile.offset * 100:.3f}%, "
            f"amplitude = {profile.amplitude * 100:.3f}%, "
            f"frequency = {profile.frequency:.3g} Hz)"
        )
    if profile_type == "drift":
        end_value = profile.offset + profile.rate * tstop
        return (
            f"drift (offset = {profile.offset * 100:.3f}%, "
            f"rate = {profile.rate * 100:.3g} %/s, "
            f"end = {end_value * 100:.3f}% at t = {tstop:.3g} s)"
        )
    if profile_type == "abrupt":
        value_after = profile.value_after if profile.value_after is not None else profile.offset + profile.amplitude
        return (
            f"abrupt step (before = {profile.offset * 100:.3f}%, "
            f"after = {value_after * 100:.3f}% at t = {profile.t_step:.3g} s)"
        )
    if profile_type == "pulse":
        return (
            f"pulse (offset = {profile.offset * 100:.3f}%, "
            f"amplitude = {profile.amplitude * 100:.3f}%, "
            f"frequency = {profile.frequency:.3g} Hz, duty = {profile.duty:.3g})"
        )
    if profile_type == "pwl":
        return (
            f"triangle PWL (offset = {profile.offset * 100:.3f}%, "
            f"amplitude = {profile.amplitude * 100:.3f}%, "
            f"frequency = {profile.frequency:.3g} Hz)"
        )
    if profile_type == "custom":
        return f"custom PWL ({len(profile.points)} points)"
    return f"dc ({profile.offset * 100:.3f}%)"


def builtin_preset_profiles(base: StrainProfileConfig, *, tstop: float) -> list[StrainProfileConfig]:
    """Return the bundled preset profiles seeded from ``base`` parameters."""
    custom_points = base.points or [
        [0.0, base.offset],
        [min(1.0, tstop * 0.2), base.offset + base.amplitude],
        [min(3.0, tstop * 0.6), base.offset + base.amplitude],
        [tstop, base.offset],
    ]
    presets: list[StrainProfileConfig] = [
        replace(base, type="sine", name="sine"),
        replace(base, type="drift", name="drift", rate=base.rate or base.amplitude / max(tstop, 1e-6)),
        replace(
            base,
            type="abrupt",
            name="abrupt",
            t_step=base.t_step or min(1.0, tstop * 0.2),
            value_after=base.value_after if base.value_after is not None else base.offset + base.amplitude,
        ),
        replace(base, type="pulse", name="pulse"),
        replace(base, type="pwl", name="pwl"),
        replace(base, type="custom", name="custom", points=custom_points),
    ]
    return presets


def resolve_transient_profiles(transient: TransientConfig) -> list[TransientProfileCase]:
    """Resolve the transient profile list from explicit or preset configuration."""
    if transient.run_all_presets:
        profiles = builtin_preset_profiles(transient.profile, tstop=transient.tstop)
    elif transient.profiles:
        profiles = transient.profiles
    else:
        profiles = [transient.profile]

    cases: list[TransientProfileCase] = []
    for profile in profiles:
        slug = profile_slug(profile)
        cases.append(TransientProfileCase(slug=slug, profile=profile))
    return cases
