#!/usr/bin/env bash
# Convert README.md to PDF (pandoc + xelatex).
#
# GitHub badge lines are omitted. The Mermaid flowchart is embedded as a PNG when
# a local renderer (mmdc / npx) is available, or when --use-kroki is passed.
#
# Usage:
#   ./scripts/readme_to_pdf.sh
#   ./scripts/readme_to_pdf.sh --output docs/README.pdf
#   ./scripts/readme_to_pdf.sh --use-kroki
#   ./scripts/readme_to_pdf.sh --no-mermaid
#   ./scripts/readme_to_pdf.sh --help
#
# Requirements: pandoc, xelatex (texlive-xetex), DejaVu fonts (fonts-dejavu).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
README="${ROOT_DIR}/README.md"
PDF_HEADER="${SCRIPT_DIR}/readme_pdf_header.tex"
OUTPUT="${ROOT_DIR}/README.pdf"
RENDER_MERMAID=1
USE_KROKI=0

usage() {
    cat <<'EOF'
Convert README.md to PDF.

Options:
  --output PATH   Output PDF path (default: <repo>/README.pdf)
  --no-mermaid    Keep the Mermaid block as source text (no diagram image)
  --use-kroki     Render Mermaid via https://kroki.io (network required)
  --help          Show this message

Mermaid render order: mmdc on PATH, then npx @mermaid-js/mermaid-cli, then Kroki
(if --use-kroki). Without any of these, the diagram stays a code block.

PDF engine: pandoc with xelatex, DejaVu Serif / DejaVu Sans Mono, and
scripts/readme_pdf_header.tex (line breaks in code/tables, column-safe tables).

Install hints (Debian/Ubuntu):
  sudo apt-get install -y pandoc texlive-xetex texlive-fonts-recommended \
    texlive-latex-extra fonts-dejavu
EOF
}

log() {
    printf '[readme_to_pdf] %s\n' "$*"
}

warn() {
    printf '[readme_to_pdf] warning: %s\n' "$*" >&2
}

die() {
    printf '[readme_to_pdf] error: %s\n' "$*" >&2
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --output)
                shift
                [[ $# -gt 0 ]] || die "--output requires a path"
                OUTPUT="$1"
                [[ "${OUTPUT}" = /* ]] || OUTPUT="${ROOT_DIR}/${OUTPUT}"
                shift
                ;;
            --no-mermaid)
                RENDER_MERMAID=0
                shift
                ;;
            --use-kroki)
                USE_KROKI=1
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

require_tools() {
    command -v pandoc >/dev/null 2>&1 || die "pandoc not found (see --help for install hints)"
    command -v xelatex >/dev/null 2>&1 || die "xelatex not found; install texlive-xetex"
}

cleanup() {
    [[ -n "${WORK_DIR:-}" && -d "${WORK_DIR}" ]] && rm -rf "${WORK_DIR}"
}

render_mermaid_local() {
    local diagram_path="$1"
    local png_path="$2"
    if command -v mmdc >/dev/null 2>&1; then
        mmdc -i "${diagram_path}" -o "${png_path}" -b transparent
        return 0
    fi
    if command -v npx >/dev/null 2>&1; then
        npx --yes @mermaid-js/mermaid-cli -i "${diagram_path}" -o "${png_path}" -b transparent
        return 0
    fi
    return 1
}

render_mermaid_kroki() {
    local diagram_path="$1"
    local png_path="$2"
    command -v curl >/dev/null 2>&1 || return 1
    curl -fsS -X POST -H "Content-Type: text/plain" \
        --data-binary @"${diagram_path}" \
        "https://kroki.io/mermaid/png" -o "${png_path}"
}

render_mermaid_png() {
    local diagram_path="$1"
    local png_path="$2"

    if render_mermaid_local "${diagram_path}" "${png_path}"; then
        log "Mermaid diagram rendered locally"
        return 0
    fi
    if [[ "${USE_KROKI}" -eq 1 ]] && render_mermaid_kroki "${diagram_path}" "${png_path}"; then
        log "Mermaid diagram rendered via Kroki"
        return 0
    fi
    return 1
}

preprocess_markdown() {
    local src="$1"
    local dst="$2"
    local mermaid_png="$3"
    local render_mermaid="$4"

    README_SRC="${src}" \
    README_DST="${dst}" \
    MERMAID_PNG="${mermaid_png}" \
    RENDER_MERMAID="${render_mermaid}" \
    python3 <<'PY'
import os
import re
from pathlib import Path

src = Path(os.environ["README_SRC"])
dst = Path(os.environ["README_DST"])
mermaid_png = Path(os.environ["MERMAID_PNG"])
render_mermaid = os.environ["RENDER_MERMAID"] == "1"

text = src.read_text(encoding="utf-8")
lines = [
    line
    for line in text.splitlines()
    if "shields.io" not in line and not line.startswith("[![")
]

# Drop the hand-written TOC; pandoc --toc emits a typeset table of contents.
filtered: list[str] = []
skip_toc = False
for line in lines:
    if line.strip() == "## Table of contents":
        skip_toc = True
        continue
    if skip_toc:
        if line.startswith("## "):
            skip_toc = False
        else:
            continue
    filtered.append(line)
lines = filtered

body = "\n".join(lines) + "\n"

pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
match = pattern.search(body)
if not match:
    dst.write_text(body, encoding="utf-8")
    raise SystemExit(0)

if render_mermaid and mermaid_png.is_file():
    replacement = (
        "![Dynamic strain extensions (Options 1–4)]("
        f"{mermaid_png.name})\n\n"
        "*Figure: dynamic strain-to-parameter signal flow.*\n"
    )
    body = body[: match.start()] + replacement + body[match.end() :]
else:
    if render_mermaid:
        print(
            "[readme_to_pdf] Mermaid diagram not rendered; kept as code block. "
            "Install mmdc/npx, or pass --use-kroki.",
            file=__import__("sys").stderr,
        )

dst.write_text(body, encoding="utf-8")
PY
}

extract_mermaid() {
    local src="$1"
    local diagram_path="$2"
    python3 -c "
import re
from pathlib import Path
text = Path('${src}').read_text(encoding='utf-8')
m = re.search(r'\`\`\`mermaid\n(.*?)\`\`\`', text, re.DOTALL)
if not m:
    raise SystemExit(1)
Path('${diagram_path}').write_text(m.group(1).strip() + '\n', encoding='utf-8')
"
}

main() {
    parse_args "$@"
    require_tools

    [[ -f "${README}" ]] || die "README not found: ${README}"

    WORK_DIR="$(mktemp -d)"
    trap cleanup EXIT

    local md_path="${WORK_DIR}/README_for_pdf.md"
    local diagram_path="${WORK_DIR}/strain_flow.mmd"
    local mermaid_png="${WORK_DIR}/strain_flow.png"

    if [[ "${RENDER_MERMAID}" -eq 1 ]]; then
        if extract_mermaid "${README}" "${diagram_path}" 2>/dev/null; then
            render_mermaid_png "${diagram_path}" "${mermaid_png}" \
                || warn "Mermaid render skipped; see --help"
        fi
    fi

    preprocess_markdown "${README}" "${md_path}" "${mermaid_png}" "${RENDER_MERMAID}"

    mkdir -p "$(dirname "${OUTPUT}")"
    [[ -f "${PDF_HEADER}" ]] || die "missing LaTeX header: ${PDF_HEADER}"

    log "Building PDF -> ${OUTPUT}"
    pandoc "${md_path}" -o "${OUTPUT}" \
        --pdf-engine=xelatex \
        --resource-path="${WORK_DIR}" \
        --include-in-header="${PDF_HEADER}" \
        -V geometry:margin=1in \
        -V fontsize=11pt \
        -V mainfont="DejaVu Serif" \
        -V monofont="DejaVu Sans Mono" \
        -V monofontoptions="Scale=0.92" \
        -V tables=true \
        -V graphics=true \
        --wrap=preserve \
        --toc \
        -V colorlinks=true \
        -V linkcolor=blue \
        --number-sections

    log "Done: ${OUTPUT}"
}

main "$@"
