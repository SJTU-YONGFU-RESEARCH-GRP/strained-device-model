"""Tests for markdown report generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from strain_spice.report import (
    TransientMetrics,
    _format_table,
    _phase_lag_seconds,
    _relative_change_pct,
    _transient_metrics,
    write_results_index,
)
from strain_spice.simulator import SimulationResult


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


def test_relative_change_pct_handles_zero_baseline() -> None:
    """Zero baseline should return finite or infinite change as appropriate."""
    assert _relative_change_pct(0.0, 0.0) == 0.0
    assert _relative_change_pct(0.0, 1.0) == float("inf")
    assert _relative_change_pct(2.0, 3.0) == pytest.approx(50.0)


def test_phase_lag_seconds_detects_delayed_response() -> None:
    """Cross-correlation should report positive lag when response trails reference."""
    time_s = np.linspace(0.0, 1.0, 101)
    reference = np.sin(2.0 * np.pi * time_s)
    delay_steps = 5
    response = np.roll(reference, delay_steps)
    response[:delay_steps] = 0.0

    lag = _phase_lag_seconds(time_s, reference, response)

    assert lag == pytest.approx(time_s[delay_steps] - time_s[0], rel=0.2)


def test_transient_metrics_computes_rms_and_peak_to_peak() -> None:
    """Transient metrics should summarize amplitude and modulation metrics."""
    time_s = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    eps_s = np.array([0.0, 0.005, 0.0, -0.005, 0.0])
    id_base = np.array([0.0002, 0.0002, 0.0002, 0.0002, 0.0002])
    id_strained = np.array([0.0002, 0.00022, 0.0002, 0.00018, 0.0002])

    baseline = SimulationResult(
        name="baseline_transient",
        columns={"time": time_s, "v(eps_s)": eps_s, "i(vdd)": -id_base},
        analysis="tran",
    )
    strained = SimulationResult(
        name="strained_transient",
        columns={"time": time_s, "v(eps_s)": eps_s, "i(vdd)": -id_strained},
        analysis="tran",
    )

    metrics = _transient_metrics(baseline, strained)

    assert isinstance(metrics, TransientMetrics)
    assert metrics.peak_baseline == pytest.approx(0.0002)
    assert metrics.peak_strained == pytest.approx(0.00022)
    assert metrics.ptp_strained == pytest.approx(4e-5)
    assert metrics.rms_strained > metrics.rms_baseline


def test_write_results_index_lists_completed_evaluations(tmp_path: Path) -> None:
    """The results index should link to reports and transient artifacts when present."""
    dynamic_dir = tmp_path / "bsim4_nmos_dynamic"
    static_dir = tmp_path / "bsim4_nmos"
    static_dir.mkdir()
    figures_dir = dynamic_dir / "figures"
    figures_dir.mkdir(parents=True)
    (dynamic_dir / "strain_comparison_report.md").write_text("# dynamic", encoding="utf-8")
    (static_dir / "strain_comparison_report.md").write_text("# static", encoding="utf-8")
    (figures_dir / "transient_comparison.svg").write_text("<svg/>", encoding="utf-8")
    (figures_dir / "magnitude_comparison.svg").write_text("<svg/>", encoding="utf-8")

    index_path = write_results_index(tmp_path)
    content = index_path.read_text(encoding="utf-8")

    assert index_path.name == "README.md"
    assert "bsim4_nmos_dynamic/strain_comparison_report.md" in content
    assert "transient_comparison.svg" in content
    assert "bsim4_nmos/strain_comparison_report.md" in content
