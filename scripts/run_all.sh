#!/usr/bin/env bash
# Run bundled strain-spice evaluations (ngspice and optional Spectre).
#
# Usage:
#   ./scripts/run_all.sh                    # ngspice suite; Spectre smoke if on PATH
#   ./scripts/run_all.sh --skip-spectre     # ngspice only
#   ./scripts/run_all.sh --with-spectre     # require Spectre smoke when possible
#   ./scripts/run_all.sh --require-spectre  # fail if spectre is missing
#   ./scripts/run_all.sh --spectre-only     # Spectre smoke only
#   ./scripts/run_all.sh --ngspice-only     # ngspice suite only (default BSIM jobs)
#   ./scripts/run_all.sh --skip-dynamic
#   ./scripts/run_all.sh --only bsim4_nmos strain_demo_spectre
#   ./scripts/run_all.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
RESULTS_DIR="${ROOT_DIR}/results"
SKIP_DYNAMIC=0
SKIP_SPECTRE=0
WITH_SPECTRE=0
REQUIRE_SPECTRE=0
SPECTRE_ONLY=0
NGSPICE_ONLY=0
ONLY=()

usage() {
    cat <<'EOF'
Run bundled strain-spice evaluations.

Ngspice jobs (BSIM reference models) write to results/<name>/.
When Spectre is enabled, a cross-simulator smoke job runs with the
behavioral strain_demo_mos model and writes to results/strain_demo_spectre/.

Options:
  --skip-spectre     Do not run Spectre validation (ngspice only)
  --with-spectre     Run Spectre smoke even if spectre is not auto-detected
  --require-spectre  Fail if spectre is not on PATH when Spectre is requested
  --spectre-only     Run only the Spectre smoke evaluation
  --ngspice-only     Run only ngspice evaluations (skip Spectre)
  --skip-dynamic     Skip configs/bsim4_nmos_dynamic.yaml
  --only NAME ...    Run only the named evaluation(s); names match results dirs
  --help             Show this message

Bundled ngspice evaluations:
  bsim3_nmos
  bsim3_pmos
  bsim4_nmos
  bsim4_pmos
  bsim4l14_nmos
  bsim4_nmos_dynamic
  transient_profiles_ngspice

Bundled Spectre evaluation (requires Cadence Spectre on PATH):
  strain_demo_spectre
  transient_profiles_spectre
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
            --skip-spectre)
                SKIP_SPECTRE=1
                shift
                ;;
            --with-spectre)
                WITH_SPECTRE=1
                shift
                ;;
            --require-spectre)
                REQUIRE_SPECTRE=1
                WITH_SPECTRE=1
                shift
                ;;
            --spectre-only)
                SPECTRE_ONLY=1
                shift
                ;;
            --ngspice-only)
                NGSPICE_ONLY=1
                SKIP_SPECTRE=1
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

ensure_strain_spice() {
    command -v strain-spice >/dev/null 2>&1 || die \
        "strain-spice not found; run ./scripts/install.sh and activate .venv"
}

ensure_ngspice() {
    command -v ngspice >/dev/null 2>&1 || die \
        "ngspice not found on PATH; install ngspice before running ngspice evaluations"
}

spectre_available() {
    command -v spectre >/dev/null 2>&1
}

should_run_spectre() {
    if [[ "$SKIP_SPECTRE" -eq 1 || "$NGSPICE_ONLY" -eq 1 ]]; then
        return 1
    fi
    if [[ "$WITH_SPECTRE" -eq 1 || "$SPECTRE_ONLY" -eq 1 ]]; then
        return 0
    fi
    spectre_available
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
    local output="$4"
    local simulator="$5"

    log "running ${name} (${simulator})"
    log "  device: ${device}"
    log "  config: ${config}"
    log "  output: ${output}"

    strain-spice run \
        --device "${ROOT_DIR}/${device}" \
        --config "${ROOT_DIR}/${config}" \
        --output "${output}" \
        --simulator "${simulator}"
}

write_results_index() {
    log "updating ${RESULTS_DIR}/README.md"
    python - <<'PY'
from pathlib import Path

from strain_spice.report import write_results_index

write_results_index(Path("results"))
PY
}

main() {
    parse_args "$@"
    cd "$ROOT_DIR"

    activate_venv_if_present
    ensure_strain_spice
    mkdir -p "$RESULTS_DIR"

    local ran=0
    local job name device config output simulator

    if [[ "$SPECTRE_ONLY" -eq 0 ]]; then
        ensure_ngspice
        local -a ngspice_jobs=(
            "bsim3_nmos|models/bsim3_nmos.subckt|configs/bsim3_nmos.yaml"
            "bsim3_pmos|models/bsim3_pmos.subckt|configs/bsim3_pmos.yaml"
            "bsim4_nmos|models/bsim4_nmos.subckt|configs/bsim4_nmos.yaml"
            "bsim4_pmos|models/bsim4_pmos.subckt|configs/bsim4_pmos.yaml"
            "bsim4l14_nmos|models/bsim4l14_nmos.subckt|configs/bsim4l14_nmos.yaml"
            "bsim4_nmos_dynamic|models/bsim4_nmos.subckt|configs/bsim4_nmos_dynamic.yaml"
            "transient_profiles_ngspice|models/bsim4_nmos.subckt|configs/transient_profiles_ngspice.yaml"
        )

        for job in "${ngspice_jobs[@]}"; do
            IFS='|' read -r name device config <<<"$job"
            if should_run "$name"; then
                run_evaluation "$name" "$device" "$config" "${RESULTS_DIR}/${name}" ngspice
                ran=$((ran + 1))
            else
                log "skipping ${name}"
            fi
        done
    fi

    if should_run_spectre; then
        if ! spectre_available; then
            if [[ "$REQUIRE_SPECTRE" -eq 1 ]]; then
                die "spectre not found on PATH; install Cadence Spectre or drop --require-spectre"
            fi
            warn "spectre not found on PATH; skipping strain_demo_spectre validation"
        else
            name="strain_demo_spectre"
            if should_run "$name"; then
                run_evaluation \
                    "$name" \
                    "models/strain_demo_mos.subckt" \
                    "configs/strain_demo.yaml" \
                    "${RESULTS_DIR}/${name}" \
                    spectre
                ran=$((ran + 1))
            else
                log "skipping ${name}"
            fi

            name="transient_profiles_spectre"
            if should_run "$name"; then
                run_evaluation \
                    "$name" \
                    "models/strain_demo_mos.subckt" \
                    "configs/transient_profiles_spectre.yaml" \
                    "${RESULTS_DIR}/${name}" \
                    spectre
                ran=$((ran + 1))
            else
                log "skipping ${name}"
            fi
        fi
    fi

    if [[ "$ran" -eq 0 ]]; then
        die "no evaluations selected; check --only names, --skip-dynamic, or simulator flags"
    fi

    write_results_index

    log "finished ${ran} evaluation(s); reports under ${RESULTS_DIR}/"
    log "results index: ${RESULTS_DIR}/README.md"
}

main "$@"
