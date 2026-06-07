#!/usr/bin/env bash
set -eo pipefail

find_conda_bin() {
  if [ -n "${IACPG_CONDA_BIN:-}" ] && [ -x "${IACPG_CONDA_BIN}" ]; then
    printf '%s\n' "$IACPG_CONDA_BIN"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return 0
  fi

  local candidates=(
    "$HOME/miniconda3/bin/conda"
    "$HOME/anaconda3/bin/conda"
    "$HOME/mambaforge/bin/conda"
    "$HOME/miniforge3/bin/conda"
  )

  local c
  for c in "${candidates[@]}"; do
    if [ -x "$c" ]; then
      printf '%s\n' "$c"
      return 0
    fi
  done

  return 1
}

CONDA_BIN="$(find_conda_bin || true)"
if [ -z "$CONDA_BIN" ]; then
  echo "conda not found. Put conda in PATH or set IACPG_CONDA_BIN." >&2
  exit 1
fi

CONDA_BASE="$($CONDA_BIN info --base 2>/dev/null)"
if [ -z "$CONDA_BASE" ] || [ ! -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
  echo "Unable to locate conda.sh via $CONDA_BIN" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONDA_BASE/etc/profile.d/conda.sh"
export IACPG_CONDA_ENV="${IACPG_CONDA_ENV:-dd}"
conda activate "$IACPG_CONDA_ENV"
