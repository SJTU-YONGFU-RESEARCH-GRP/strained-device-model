"""Tests for SPICE subcircuit parsing."""

from __future__ import annotations

from strain_spice.parser import parse_subckt


def test_parse_first_subckt() -> None:
    """Parse the first subcircuit in a netlist."""
    source = """
    * comment
    .subckt my_device d g s
    R1 d s 1k
    .ends my_device
    """
    parsed = parse_subckt(source)
    assert parsed.name == "my_device"
    assert parsed.ports == ("d", "g", "s")
