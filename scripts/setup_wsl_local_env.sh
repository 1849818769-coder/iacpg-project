#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIR="${IACPG_BASE:-$HOME/.local/iacpg}"
BIN_DIR="$BASE_DIR/bin"
ENV_DIR="$BASE_DIR/envs"
TOOLS_DIR="$BASE_DIR/tools"
DOWNLOAD_DIR="$BASE_DIR/downloads"
MICROMAMBA_BIN="$BIN_DIR/micromamba"
ENV_PREFIX="$ENV_DIR/dd"
JDK_DIR="$TOOLS_DIR/jdk-17"
JOERN_DIR="$TOOLS_DIR/joern-cli"
FAKE_LIBC_DIR="$TOOLS_DIR/fake_libc_include"

JOERN_VERSION="v4.0.504"
PYCPARSER_VERSION="2.22"
JDK_URL="https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
MICROMAMBA_URL="https://micro.mamba.pm/api/micromamba/linux-64/latest"
JOERN_URL="https://github.com/joernio/joern/releases/download/${JOERN_VERSION}/joern-cli.zip"
PYCPARSER_URL="https://github.com/eliben/pycparser/archive/refs/tags/release_v${PYCPARSER_VERSION}.tar.gz"

mkdir -p "$BIN_DIR" "$ENV_DIR" "$TOOLS_DIR" "$DOWNLOAD_DIR"

download_micromamba() {
  if [ -x "$MICROMAMBA_BIN" ]; then
    return 0
  fi

  local archive_dir="$DOWNLOAD_DIR/micromamba"
  rm -rf "$archive_dir"
  mkdir -p "$archive_dir"
  curl -L "$MICROMAMBA_URL" | tar -xvj -C "$archive_dir" >/dev/null
  install "$archive_dir/bin/micromamba" "$MICROMAMBA_BIN"
}

create_env() {
  if [ ! -x "$MICROMAMBA_BIN" ]; then
    echo "micromamba is missing: $MICROMAMBA_BIN" >&2
    exit 1
  fi

  if [ ! -d "$ENV_PREFIX" ]; then
    "$MICROMAMBA_BIN" create -y -p "$ENV_PREFIX" python=3.11 pip
  fi

  "$MICROMAMBA_BIN" run -p "$ENV_PREFIX" python -m pip install --upgrade pip setuptools wheel
  "$MICROMAMBA_BIN" run -p "$ENV_PREFIX" python -m pip install \
    chardet==5.2.0 \
    cpgqls-client==0.0.9 \
    mcp==1.26.0 \
    psutil==7.1.3 \
    pycparser==2.22 \
    pytest==9.0.1 \
    pytest-timeout==2.4.0 \
    pyyaml==6.0.3 \
    requests==2.32.5 \
    tree-sitter==0.22.3 \
    tree-sitter-c==0.21.4 \
    z3-solver==4.14.1.0
}

install_jdk() {
  if [ -x "$JDK_DIR/bin/java" ]; then
    return 0
  fi

  local archive="$DOWNLOAD_DIR/jdk17.tar.gz"
  local extract_dir="$DOWNLOAD_DIR/jdk17"
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  curl -L "$JDK_URL" -o "$archive"
  tar -xzf "$archive" -C "$extract_dir"
  rm -rf "$JDK_DIR"
  mv "$extract_dir"/jdk-* "$JDK_DIR"
}

install_joern() {
  if [ -x "$JOERN_DIR/bin/joern" ]; then
    return 0
  fi

  local archive="$DOWNLOAD_DIR/joern-cli.zip"
  curl -L "$JOERN_URL" -o "$archive"
  rm -rf "$JOERN_DIR"
  "$MICROMAMBA_BIN" run -p "$ENV_PREFIX" python -c "import shutil, zipfile; archive = r'$archive'; target = r'$TOOLS_DIR'; shutil.rmtree(r'$JOERN_DIR', ignore_errors=True); zipfile.ZipFile(archive).extractall(target)"
}

install_fake_libc_headers() {
  if [ -d "$FAKE_LIBC_DIR" ] && [ -f "$FAKE_LIBC_DIR/stdio.h" ]; then
    return 0
  fi

  local archive="$DOWNLOAD_DIR/pycparser-${PYCPARSER_VERSION}.tar.gz"
  local extract_dir="$DOWNLOAD_DIR/pycparser-${PYCPARSER_VERSION}"
  curl -L "$PYCPARSER_URL" -o "$archive"
  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  tar -xzf "$archive" -C "$extract_dir"
  rm -rf "$FAKE_LIBC_DIR"
  mkdir -p "$FAKE_LIBC_DIR"
  cp -R "$extract_dir"/pycparser-release_v${PYCPARSER_VERSION}/utils/fake_libc_include/. "$FAKE_LIBC_DIR/"
}

download_micromamba
create_env
install_jdk
install_joern
install_fake_libc_headers

cat <<EOF
Local WSL environment is ready.

Repo root: $ROOT_DIR
Micromamba: $MICROMAMBA_BIN
Env prefix: $ENV_PREFIX
Java home: $JDK_DIR
Joern home: $JOERN_DIR
Fake libc: $FAKE_LIBC_DIR

Next step:
  source "$ROOT_DIR/scripts/use_local_env.sh"
EOF
