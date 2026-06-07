#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "source this file instead of executing it:" >&2
  echo "  source scripts/use_local_env.sh" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIR="${IACPG_BASE:-$HOME/.local/iacpg}"
MICROMAMBA_BIN="$BASE_DIR/bin/micromamba"
ENV_PREFIX="$BASE_DIR/envs/dd"
JAVA_HOME_LOCAL="$BASE_DIR/tools/jdk-17"
JOERN_HOME_LOCAL="$BASE_DIR/tools/joern-cli"
FAKE_LIBC_DIR="$BASE_DIR/tools/fake_libc_include"

if [ ! -x "$MICROMAMBA_BIN" ]; then
  echo "micromamba not found: $MICROMAMBA_BIN" >&2
  return 1
fi

if [ ! -d "$ENV_PREFIX" ]; then
  echo "environment not found: $ENV_PREFIX" >&2
  echo "run scripts/setup_wsl_local_env.sh first" >&2
  return 1
fi

eval "$($MICROMAMBA_BIN shell hook -s bash)"
micromamba activate "$ENV_PREFIX"

export IACPG_ROOT="$ROOT_DIR"
export IACPG_BASE="$BASE_DIR"
export IACPG_CONDA_ENV="dd"
export CONDA_DEFAULT_ENV="dd"
export JAVA_HOME="$JAVA_HOME_LOCAL"
export JOERN_HOME="$JOERN_HOME_LOCAL"
export JOERN_PARSE="$JOERN_HOME_LOCAL/joern-parse"
export JOERN_EXPORT="$JOERN_HOME_LOCAL/joern-export"
export IACPG_FAKE_LIBC_INCLUDE="$FAKE_LIBC_DIR"

case ":${PATH}:" in
  *":$JOERN_HOME_LOCAL:"*) ;;
  *) export PATH="$JOERN_HOME_LOCAL:$JOERN_HOME_LOCAL/bin:$JAVA_HOME_LOCAL/bin:$PATH" ;;
esac

case ":${PYTHONPATH:-}:" in
  *":$ROOT_DIR:"*|"$ROOT_DIR:"*|*":$ROOT_DIR"|"$ROOT_DIR") ;;
  *) export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" ;;
esac

echo "Activated local iacpg environment:"
echo "  python: $(command -v python)"
echo "  java:   $(command -v java)"
echo "  joern:  $(command -v joern)"
