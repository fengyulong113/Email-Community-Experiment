#!/usr/bin/env bash
# Run with Bash (Git Bash on Windows), not with `sh run_all.sh`.
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: bash run_all.sh [--check] [--python PATH] [--help]

Run preprocessing, clustering, evaluation, metric plots and case analysis.
  --check        Check inputs and dependencies without running experiments.
  --python PATH  Use this Python executable (relative paths use project root).
  --help         Show this help.

Default Python: project .venv, then python3/python from PATH.
Existing generated results are overwritten. Raw inputs are read only.
EOF
}

CHECK_ONLY=0
PYTHON_BIN=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) CHECK_ONLY=1; shift ;;
        --python)
            if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
                printf 'ERROR: --python requires an executable path.\n' >&2
                exit 2
            fi
            PYTHON_BIN="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'ERROR: unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
done

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$PROJECT_DIR"

if [[ -z "$PYTHON_BIN" ]]; then
    if [[ -x .venv/bin/python ]]; then
        PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
    elif [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]] && [[ -f .venv/Scripts/python.exe ]]; then
        PYTHON_BIN="$PROJECT_DIR/.venv/Scripts/python.exe"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    else
        printf 'ERROR: Python not found. See README.md for environment setup.\n' >&2
        exit 1
    fi
fi

# Keep Python output readable in Windows terminals and captured logs.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export MPLBACKEND=Agg

SCRIPTS=(
    prepare_data.py
    run_clustering.py
    evaluate_clustering.py
    plot_metrics.py
    analyze_community.py
)

for INPUT_FILE in data/raw/email-Eu-core.txt data/raw/email-Eu-core-department-labels.txt; do
    if [[ ! -s "$INPUT_FILE" ]]; then
        printf 'ERROR: missing or empty input: %s\nDownload and extract the data as described in README.md.\n' "$INPUT_FILE" >&2
        exit 1
    fi
done
for SCRIPT in "${SCRIPTS[@]}"; do
    if [[ ! -f "src/$SCRIPT" ]]; then
        printf 'ERROR: missing script: src/%s\n' "$SCRIPT" >&2
        exit 1
    fi
done

printf 'Project: %s\nPython: %s\n' "$PROJECT_DIR" "$PYTHON_BIN"
if "$PYTHON_BIN" - <<'PY'
import importlib
import inspect
import platform
import sys

print("Python version:", platform.python_version())
failed = []
for name, package in [
    ("networkx", "networkx"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("matplotlib", "matplotlib"),
    ("scipy", "scipy"),
]:
    try:
        module = importlib.import_module(name)
        print(f"{package}: {module.__version__}")
    except Exception as error:
        failed.append(f"{package}: {error}")

if not failed:
    import networkx as nx
    if not hasattr(nx.community, "louvain_communities"):
        failed.append("NetworkX lacks louvain_communities")
    if "method" not in inspect.signature(nx.spring_layout).parameters:
        failed.append("NetworkX is too old for spring_layout(method=...)")

if failed:
    print("Dependency check failed:\n" + "\n".join(failed), file=sys.stderr)
    print("Install requirements.txt using the selected Python interpreter.", file=sys.stderr)
    sys.exit(1)
PY
then
    printf 'Input and dependency checks passed.\n'
else
    printf 'ERROR: Python/dependency check failed. See README.md.\n' >&2
    exit 1
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
    printf 'Check complete. No experiment stages were run.\n'
    exit 0
fi

mkdir -p results/logs
LOG_FILE="results/logs/run_$(date -u +%Y%m%dT%H%M%SZ)_$$.log"
printf 'Started (UTC): %s\nPython: %s\nExisting generated results will be overwritten.\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PYTHON_BIN" | tee "$LOG_FILE"

STEP=0
for SCRIPT in "${SCRIPTS[@]}"; do
    STEP=$((STEP + 1))
    printf '\n[%s/%s] %s\n' "$STEP" "${#SCRIPTS[@]}" "$SCRIPT" | tee -a "$LOG_FILE"
    if "$PYTHON_BIN" -u "src/$SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
        :
    else
        STATUS=$?
        printf 'ERROR: stage %s failed (exit %s). Later stages were not run. Log: %s\n' \
            "$SCRIPT" "$STATUS" "$LOG_FILE" >&2
        exit "$STATUS"
    fi
done

printf '\nAll 5 stages completed.\nTables: results/evaluation/report_tables.txt\nCase: results/case_study/case_report.txt\nFigures: results/figures/\nLog: %s\n' "$LOG_FILE" | tee -a "$LOG_FILE"
