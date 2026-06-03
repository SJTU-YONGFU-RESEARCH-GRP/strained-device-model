#!/usr/bin/env bash
# Run all bundled strain-spice evaluations (static + dynamic configs).
#
# Usage:
#   ./scripts/run_all.sh              # run every bundled config
#   ./scripts/run_all.sh --skip-dynamic
#   ./scripts/run_all.sh --only bsim4_nmos bsim4_nmos_dynamic
#   ./scripts/run_all.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
RESULTS_DIR="${ROOT_DIR}/results"
SKIP_DYNAMIC=0
ONLY=()

usage() {
    cat <<'EOF'
Run all bundled strain-spice evaluations.

Each job generates netlists, runs ngspice, plots figures, and writes a report
under results/<name>/.

Options:
  --skip-dynamic   Skip configs/bsim4_nmos_dynamic.yaml
  --only NAME ...  Run only the named evaluation(s); names match results dirs
  --help           Show this message

Bundled evaluations:
  bsim3_nmos
  bsim3_pmos
  bsim4_nmos
  bsim4_pmos
  bsim4l14_nmos
  bsim4_nmos_dynamic
EOF
}

log() {
    printf '[run_all] %s\n' "$*"
}

warn() {
    printf '[run_all] warning: %s\n' "$*" >&2
}

die() {
    printf '[run_all] error: %s\n' "$*" >&2
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-dynamic)
                SKIP_DYNAMIC=1
                shift
                ;;
            --only)
                shift
                [[ $# -gt 0 ]] || die "--only requires at least one evaluation name"
                while [[ $# -gt 0 && "$1" != --* ]]; do
                    ONLY+=("$1")
                    shift
                done
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

activate_venv_if_present() {
    if [[ -f "${VENV_DIR}/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "${VENV_DIR}/bin/activate"
        log "using virtual environment at ${VENV_DIR}"
    fi
}

ensure_prerequisites() {
    command -v strain-spice >/dev/null 2>&1 || die \
        "strain-spice not found; run ./scripts/install.sh and activate .venv"
    command -v ngspice >/dev/null 2>&1 || die \
        "ngspice not found on PATH; install ngspice before running evaluations"
}

should_run() {
    local name="$1"

    if [[ "$SKIP_DYNAMIC" -eq 1 && "$name" == "bsim4_nmos_dynamic" ]]; then
        return 1
    fi

    if [[ ${#ONLY[@]} -eq 0 ]]; then
        return 0
    fi

    local selected
    for selected in "${ONLY[@]}"; do
        if [[ "$selected" == "$name" ]]; then
            return 0
        fi
    done
    return 1
}

run_evaluation() {
    local name="$1"
    local device="$2"
    local config="$3"
    local output="${RESULTS_DIR}/${name}"

    log "running ${name}"
    log "  device: ${device}"
    log "  config: ${config}"
    log "  output: ${output}"

    strain-spice run \
        --device "${ROOT_DIR}/${device}" \
        --config "${ROOT_DIR}/${config}" \
        --output "${output}"
}

main() {
    parse_args "$@"
    cd "$ROOT_DIR"

    activate_venv_if_present
    ensure_prerequisites
    mkdir -p "$RESULTS_DIR"

    local -a jobs=(
        "bsim3_nmos|models/bsim3_nmos.subckt|configs/bsim3_nmos.yaml"
        "bsim3_pmos|models/bsim3_pmos.subckt|configs/bsim3_pmos.yaml"
        "bsim4_nmos|models/bsim4_nmos.subckt|configs/bsim4_nmos.yaml"
        "bsim4_pmos|models/bsim4_pmos.subckt|configs/bsim4_pmos.yaml"
        "bsim4l14_nmos|models/bsim4l14_nmos.subckt|configs/bsim4l14_nmos.yaml"
        "bsim4_nmos_dynamic|models/bsim4_nmos.subckt|configs/bsim4_nmos_dynamic.yaml"
    )

    local ran=0
    local job name device config
    for job in "${jobs[@]}"; do
        IFS='|' read -r name device config <<<"$job"
        if should_run "$name"; then
            run_evaluation "$name" "$device" "$config"
            ran=$((ran + 1))
        else
            log "skipping ${name}"
        fi
    done

    if [[ "$ran" -eq 0 ]]; then
        die "no evaluations selected; check --only names or --skip-dynamic"
    fi

    log "finished ${ran} evaluation(s); reports under ${RESULTS_DIR}/"
}

main "$@"
