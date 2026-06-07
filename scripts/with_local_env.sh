#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIR="${IACPG_BASE:-$HOME/.local/iacpg}"
MICROMAMBA_BIN="$BASE_DIR/bin/micromamba"
ENV_PREFIX="$BASE_DIR/envs/dd"
JAVA_HOME_LOCAL="$BASE_DIR/tools/jdk-17"
JOERN_HOME_LOCAL="$BASE_DIR/tools/joern-cli"
FAKE_LIBC_DIR="$BASE_DIR/tools/fake_libc_include"
ENV_BIN="$ENV_PREFIX/bin"

if [ "$#" -eq 0 ]; then
  echo "usage: scripts/with_local_env.sh <command> [args...]" >&2
  exit 1
fi

exec "$MICROMAMBA_BIN" run -p "$ENV_PREFIX" env \
  CONDA_DEFAULT_ENV=dd \
  IACPG_CONDA_ENV=dd \
  JAVA_HOME="$JAVA_HOME_LOCAL" \
  JOERN_HOME="$JOERN_HOME_LOCAL" \
  JOERN_PARSE="$JOERN_HOME_LOCAL/joern-parse" \
  JOERN_EXPORT="$JOERN_HOME_LOCAL/joern-export" \
  IACPG_FAKE_LIBC_INCLUDE="$FAKE_LIBC_DIR" \
  PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  PATH="$ENV_BIN:$JOERN_HOME_LOCAL:$JOERN_HOME_LOCAL/bin:$JAVA_HOME_LOCAL/bin:$PATH" \
  "$@"
