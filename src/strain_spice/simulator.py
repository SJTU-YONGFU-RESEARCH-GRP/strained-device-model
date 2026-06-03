"""Run ngspice simulations and parse tabular output."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SimulationResult:
    """Parsed ngspice DC sweep data."""

    name: str
    columns: dict[str, np.ndarray]

    @property
    def row_count(self) -> int:
        """Return number of parsed rows."""
        if not self.columns:
            return 0
        return len(next(iter(self.columns.values())))


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


def parse_print_table(output: str, name: str) -> SimulationResult:
    """Parse ngspice ``Index`` tables from batch output."""
    lines = output.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if line.strip().startswith("Index"):
            header_index = index
            break

    if header_index is None:
        raise ValueError(f"No ngspice .print table found for '{name}'.")

    header = lines[header_index].split()
    if header[0].lower() != "index":
        raise ValueError(f"Unexpected table header for '{name}': {lines[header_index]}")

    column_names = header[1:]
    rows: list[list[float]] = []
    for line in lines[header_index + 1 :]:
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
        if not parts[0].isdigit():
            if rows:
                break
            continue
        rows.append([float(value) for value in parts[1 : 1 + len(column_names)]])

    if not rows:
        raise ValueError(f"Empty ngspice table for '{name}'.")

    data = np.array(rows, dtype=float)
    columns = {name_: data[:, idx] for idx, name_ in enumerate(column_names)}
    return SimulationResult(name=name, columns=columns)


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
        for key in ("i(vdd)", "vdd#branch"):
            if key in lowered:
                return lowered[key]
    raise KeyError(f"None of {candidates} found in columns: {list(result.columns)}")
