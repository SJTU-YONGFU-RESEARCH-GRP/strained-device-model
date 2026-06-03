"""Tests for netlist generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from strain_spice.config import StrainSpiceConfig
from strain_spice.generator import generate_netlists
from strain_spice.parser import load_device_netlist, parse_subckt


@pytest.fixture
def project_root() -> Path:
    """Return repository root."""
    return Path(__file__).resolve().parents[1]


def test_generate_wrapper_contains_strain_engine(project_root: Path, tmp_path: Path) -> None:
    """Generated wrapper should include the strain engine and user device."""
    device_path = project_root / "models" / "bsim3_nmos.subckt"
    config = StrainSpiceConfig.from_yaml(project_root / "configs" / "bsim3_nmos.yaml")
    device = parse_subckt(load_device_netlist(device_path), config.device.subckt)

    netlists = generate_netlists(device, device_path, config, tmp_path)
    wrapper_text = netlists.wrapper.read_text(encoding="utf-8")

    assert "strain_engine_spice" in wrapper_text
    assert "strain_aware_device" in wrapper_text
    assert "ddt(V(n_eps_t))" in wrapper_text
    assert "bsim3_nmos" in wrapper_text
    assert netlists.strained_magnitude_tb.exists()


def test_generate_spectre_wrapper_uses_verilog_a(project_root: Path, tmp_path: Path) -> None:
    """Spectre netlists should use the Verilog-A strain engine."""
    device_path = project_root / "models" / "strain_demo_mos.subckt"
    config = StrainSpiceConfig.from_yaml(project_root / "configs" / "strain_demo.yaml")
    config.simulator = "spectre"
    device = parse_subckt(load_device_netlist(device_path), config.device.subckt)

    netlists = generate_netlists(device, device_path, config, tmp_path)
    wrapper_text = netlists.wrapper.read_text(encoding="utf-8")

    assert "ahdl_include" in wrapper_text
    assert "strain_engine" in wrapper_text
    assert "strain_engine_spice" not in wrapper_text
    assert (tmp_path / "strain_engine.va").exists()
    assert netlists.strained_magnitude_tb.suffix == ".scs"
    assert "simulator lang=spice" in netlists.strained_magnitude_tb.read_text(encoding="utf-8")

