#!/usr/bin/env bash

# Prefer caller-provided JAVA_HOME/joern binaries; otherwise discover from PATH.
if [ -z "${JAVA_HOME:-}" ] && command -v java >/dev/null 2>&1; then
  JAVA_BIN="$(command -v java)"
  JAVA_HOME="$(cd "$(dirname "$JAVA_BIN")/.." && pwd)"
  export JAVA_HOME
fi

export PATH="$HOME/.local/bin:${JAVA_HOME:+$JAVA_HOME/bin:}$PATH"

echo "JAVA_HOME=${JAVA_HOME:-unset}"
echo "joern=$(command -v joern || true)"
echo "joern-parse=$(command -v joern-parse || true)"
echo "joern-export=$(command -v joern-export || true)"
