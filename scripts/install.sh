#!/usr/bin/env bash
# Install strain-spice and its Python dependencies.
#
# Usage:
#   ./install.sh              # editable install with dev extras (default)
#   ./install.sh --prod         # editable install without dev extras
#   ./install.sh --with-ngspice # also install ngspice via apt/brew when missing
#   ./install.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON="${PYTHON:-python3}"
PIP="${PIP:-pip}"
INSTALL_DEV=1
INSTALL_NGSPICE=0

usage() {
    cat <<'EOF'
Install strain-spice (Python package + optional ngspice check).

Options:
  --prod           Install without dev dependencies (pytest, ruff)
  --with-ngspice   Attempt to install ngspice via apt or Homebrew if missing
  --help           Show this message

Environment:
  PYTHON           Python interpreter (default: python3)
  PIP              Pip executable (default: pip)
EOF
}

log() {
    printf '[install] %s\n' "$*"
}

warn() {
    printf '[install] warning: %s\n' "$*" >&2
}

die() {
    printf '[install] error: %s\n' "$*" >&2
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --prod)
                INSTALL_DEV=0
                shift
                ;;
            --with-ngspice)
                INSTALL_NGSPICE=1
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                die "unknown option: $1 (try --help)"
                ;;
        esac
    done
}

python_version_ok() {
    "$PYTHON" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit(1)
PY
}

ensure_python() {
    command -v "$PYTHON" >/dev/null 2>&1 || die "Python not found: $PYTHON"
    python_version_ok || die "Python 3.10+ required (found: $("$PYTHON" --version 2>&1))"
    log "using $("$PYTHON" --version 2>&1)"
}

ensure_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        log "creating virtual environment at $VENV_DIR"
        "$PYTHON" -m venv "$VENV_DIR"
    else
        log "reusing virtual environment at $VENV_DIR"
    fi

    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"
}

install_python_package() {
    log "upgrading pip"
    "$PIP" install --upgrade pip

    if [[ "$INSTALL_DEV" -eq 1 ]]; then
        log "installing strain-spice in editable mode with dev extras"
        "$PIP" install -e ".[dev]"
    else
        log "installing strain-spice in editable mode"
        "$PIP" install -e .
    fi
}

detect_os() {
    case "$(uname -s)" in
        Linux) echo "linux" ;;
        Darwin) echo "macos" ;;
        *) echo "unknown" ;;
    esac
}

try_install_ngspice() {
    local os
    os="$(detect_os)"

    case "$os" in
        linux)
            if command -v apt-get >/dev/null 2>&1; then
                log "installing ngspice via apt-get"
                sudo apt-get update
                sudo apt-get install -y ngspice
                return 0
            fi
            ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                log "installing ngspice via Homebrew"
                brew install ngspice
                return 0
            fi
            ;;
    esac

    warn "could not auto-install ngspice on this system"
    warn "install ngspice manually: https://ngspice.sourceforge.io/"
    return 1
}

ensure_ngspice() {
    if command -v ngspice >/dev/null 2>&1; then
        log "found ngspice: $(ngspice -v 2>&1 | head -n 1 || true)"
        return 0
    fi

    if [[ "$INSTALL_NGSPICE" -eq 1 ]]; then
        try_install_ngspice || true
    fi

    if command -v ngspice >/dev/null 2>&1; then
        log "found ngspice: $(ngspice -v 2>&1 | head -n 1 || true)"
        return 0
    fi

    warn "ngspice not found on PATH"
    warn "simulations will fail until ngspice is installed"
    warn "re-run with --with-ngspice or install manually, then verify with: ngspice -v"
}

verify_install() {
    if command -v strain-spice >/dev/null 2>&1; then
        log "strain-spice CLI installed"
        strain-spice --help >/dev/null 2>&1 || warn "strain-spice --help failed"
    else
        warn "strain-spice CLI not found on PATH after install"
        warn "activate the venv with: source .venv/bin/activate"
    fi
}

print_next_steps() {
    cat <<EOF

Installation complete.

Activate the environment:
  source .venv/bin/activate

Run a bundled evaluation:
  strain-spice run \\
    --device models/bsim4_nmos.subckt \\
    --config configs/bsim4_nmos.yaml \\
    --output results/bsim4_nmos

Run all bundled evaluations:
  ./scripts/run_all.sh

Run tests (dev install):
  pytest

EOF
}

main() {
    parse_args "$@"
    cd "$ROOT_DIR"

    ensure_python
    ensure_venv
    install_python_package
    ensure_ngspice
    verify_install
    print_next_steps
}

main "$@"
