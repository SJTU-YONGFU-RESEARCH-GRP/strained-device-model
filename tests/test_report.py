"""Tests for markdown report generation."""

from __future__ import annotations

from strain_spice.report import _format_table


def test_format_table_escapes_pipe_characters_in_cells() -> None:
    """Pipe characters inside cells must not break markdown table columns."""
    table = _format_table(
        ["Case", "Baseline |I_D| [A]", "Relative change [%]"],
        [["Strain magnitude sweep", "0.00024057", "4.507"]],
    )

    assert "Baseline &#124;I_D&#124; [A]" in table
    header, separator, _data = table.splitlines()
    assert header.count("|") == 4
    assert separator == "| --- | --- | --- |"
