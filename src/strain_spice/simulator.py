"""Run ngspice or Spectre simulations and parse tabular output."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from strain_spice.config import SimulatorKind, StrainSpiceConfig


@dataclass(frozen=True)
class SimulationResult:
    """Parsed simulator tabular output."""

    name: str
    columns: dict[str, np.ndarray]
    analysis: str = "dc"

    @property
    def row_count(self) -> int:
        """Return number of parsed rows."""
        if not self.columns:
            return 0
        return len(next(iter(self.columns.values())))


class CircuitSimulator(Protocol):
    """Batch circuit simulator interface."""

    def run(self, netlist_path: Path, workdir: Path | None = None) -> str:
        """Run a netlist and return text used for table parsing."""
        ...


class NgspiceRunner:
    """Execute ngspice in batch mode."""

    def __init__(self, binary: str = "ngspice") -> None:
        """Initialize the runner."""
        self.binary = binary

    def run(self, netlist_path: Path, workdir: Path | None = None) -> str:
        """Run ngspice on a netlist and return combined stdout/stderr."""
        cwd = workdir or netlist_path.parent
        completed = subprocess.run(
            [self.binary, "-b", netlist_path.name],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout + "\n" + completed.stderr
        if completed.returncode != 0 and "Error" in output:
            raise RuntimeError(
                f"ngspice failed for {netlist_path.name}:\n{output.strip()}"
            )
        return output


class SpectreRunner:
    """Execute Cadence Spectre in batch mode."""

    def __init__(self, binary: str = "spectre") -> None:
        """Initialize the runner."""
        self.binary = binary

    def run(self, netlist_path: Path, workdir: Path | None = None) -> str:
        """Run Spectre and return log text plus any ``.print`` artifact content."""
        cwd = workdir or netlist_path.parent
        completed = subprocess.run(
            [self.binary, "+log", netlist_path.name],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout + "\n" + completed.stderr
        print_path = _find_spectre_print_file(cwd, netlist_path.stem)
        if print_path is not None:
            output = output + "\n" + print_path.read_text(encoding="utf-8", errors="replace")

        if completed.returncode != 0:
            if re.search(r"\b(ERROR|FATAL)\b", output, flags=re.IGNORECASE):
                raise RuntimeError(
                    f"Spectre failed for {netlist_path.name}:\n{output.strip()}"
                )
        return output


def create_runner(config: StrainSpiceConfig) -> CircuitSimulator:
    """Return the circuit simulator backend selected in the configuration."""
    simulator = config.normalized_simulator()
    if simulator == "ngspice":
        return NgspiceRunner(binary=config.ngspice_binary)
    return SpectreRunner(binary=config.spectre_binary)


def _find_spectre_print_file(workdir: Path, stem: str) -> Path | None:
    """Locate a Spectre ``.print`` or ``.mt0`` table written beside the netlist."""
    candidates = [
        workdir / f"{stem}.print",
        workdir / f"{stem}.mt0",
        workdir / "raw" / f"{stem}.print",
        workdir / "raw" / f"{stem}.mt0",
    ]
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def parse_print_table(output: str, name: str, analysis: str = "dc") -> SimulationResult:
    """Parse simulator tabular output (ngspice log or Spectre ``.print`` file)."""
    lines = output.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith("index"):
            header_index = index
            break
        if _looks_like_table_header(stripped):
            header_index = index
            break

    if header_index is None:
        raise ValueError(f"No simulation .print table found for '{name}'.")

    header = lines[header_index].split()
    if header[0].lower() == "index":
        column_names = header[1:]
        data_start = header_index + 1
    else:
        column_names = header
        data_start = header_index + 1

    rows: list[list[float]] = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Total ") or stripped.startswith("Doing analysis"):
            break
        if set(stripped) <= {"-", " "}:
            continue
        parts = stripped.split()
        if not parts:
            continue
        if header[0].lower() == "index":
            if not parts[0].isdigit():
                if rows:
                    break
                continue
            values = parts[1 : 1 + len(column_names)]
        else:
            try:
                values = [float(part) for part in parts[: len(column_names)]]
            except ValueError:
                if rows:
                    break
                continue
        if len(values) != len(column_names):
            continue
        rows.append([float(value) for value in values])

    if not rows:
        raise ValueError(f"Empty simulation table for '{name}'.")

    data = np.array(rows, dtype=float)
    columns = {name_: data[:, idx] for idx, name_ in enumerate(column_names)}
    return SimulationResult(name=name, columns=columns, analysis=analysis)


def _looks_like_table_header(line: str) -> bool:
    """Return True when a line looks like a Spectre column header row."""
    tokens = line.split()
    if len(tokens) < 2:
        return False
    if tokens[0].lower() == "index":
        return True
    allowed_prefixes = ("v(", "i(", "time", "freq")
    return any(token.lower().startswith(allowed_prefixes) for token in tokens)


def save_csv(result: SimulationResult, path: Path) -> None:
    """Write simulation columns to CSV."""
    headers = list(result.columns.keys())
    matrix = np.column_stack([result.columns[header] for header in headers])
    header_line = ",".join(headers)
    np.savetxt(path, matrix, delimiter=",", header=header_line, comments="")


def find_column(result: SimulationResult, candidates: tuple[str, ...]) -> np.ndarray:
    """Return the first matching column from a result table."""
    lowered = {key.lower(): value for key, value in result.columns.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    if "i(vdd)" in candidates or "vdd#branch" in candidates:
        for key in ("i(vdd)", "vdd#branch", 'i("vdd:p")', "i(vdd:p)"):
            if key in lowered:
                return lowered[key]
    raise KeyError(f"None of {candidates} found in columns: {list(result.columns)}")
