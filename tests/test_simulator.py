"""Tests for simulator output parsing."""

from __future__ import annotations

import pytest

from strain_spice.simulator import parse_print_table


def test_parse_ngspice_index_table() -> None:
    """Parse classic ngspice Index tables from batch logs."""
    output = """
Doing analysis dc

Index   v(eps_s)    v(alpha)    i(Vdd)
0       0           0           -1.2e-05
1       0.0005      0           -1.1e-05
"""
    result = parse_print_table(output, name="demo", analysis="dc")
    assert result.row_count == 2
    assert "v(eps_s)" in result.columns
    assert result.columns["i(Vdd)"][0] == pytest.approx(-1.2e-05)


def test_parse_spectre_header_table() -> None:
    """Parse Spectre-style tables without an Index column."""
    output = """
v(eps_s) v(alpha) i("Vdd:p")
0 0 -2.5e-06
0.001 0 -2.4e-06
"""
    result = parse_print_table(output, name="demo", analysis="dc")
    assert result.row_count == 2
    assert 'i("Vdd:p")' in result.columns


def test_parse_spectre_print_file_with_units() -> None:
    """Parse Spectre .print tables that use SI unit suffixes."""
    output = """
x
             dc       v(eps_s)       v(alpha)         i(Vdd)
              0              0              0        -40.8 u
          625 u          625 u              0        -40.8 u
            5 m            5 m              0        -40.8 u
y
"""
    result = parse_print_table(output, name="demo", analysis="dc")
    assert result.row_count == 3
    assert result.columns["v(eps_s)"][2] == pytest.approx(0.005)
    assert result.columns["i(Vdd)"][0] == pytest.approx(-40.8e-6)
