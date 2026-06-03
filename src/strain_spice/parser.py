"""Parse SPICE subcircuit definitions from user netlists."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SUBCKT_PATTERN = re.compile(
    r"^\s*\.subckt\s+(\S+)\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_ENDS_PATTERN = re.compile(
    r"^\s*\.ends(?:\s+(\S+))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class SubcktDefinition:
    """Parsed subcircuit metadata."""

    name: str
    ports: tuple[str, ...]
    body: str


def parse_subckt(source: str, subckt_name: str | None = None) -> SubcktDefinition:
    """Extract a subcircuit definition from SPICE source text.

    Args:
        source: Full SPICE file contents.
        subckt_name: Optional explicit subcircuit name. If omitted, the first
            ``.subckt`` block is used.

    Returns:
        Parsed subcircuit metadata including the original body text.

    Raises:
        ValueError: If no matching subcircuit is found.
    """
    matches = list(_SUBCKT_PATTERN.finditer(source))
    if not matches:
        raise ValueError("No .subckt definition found in device netlist.")

    for match in matches:
        name = match.group(1)
        if subckt_name is not None and name.lower() != subckt_name.lower():
            continue

        start = match.start()
        ends = _ENDS_PATTERN.search(source, match.end())
        if ends is None:
            raise ValueError(f"Missing .ends for subcircuit '{name}'.")

        body = source[start : ends.end()].strip()
        ports = tuple(match.group(2).split())
        return SubcktDefinition(name=name, ports=ports, body=body)

    available = ", ".join(match.group(1) for match in matches)
    raise ValueError(
        f"Subcircuit '{subckt_name}' not found. Available subcircuits: {available}."
    )


def load_device_netlist(path: Path) -> str:
    """Read a device netlist file."""
    return path.read_text(encoding="utf-8")
