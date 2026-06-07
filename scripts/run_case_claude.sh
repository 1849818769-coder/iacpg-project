#!/usr/bin/env bash
# 用法: bash scripts/run_case_claude.sh <case_path> [cpg]
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE_PATH="$1"
MODE="${2:-iacpg}"

if [ -z "$CASE_PATH" ]; then
  echo "Usage: $0 <case_path> [cpg]" >&2
  exit 1
fi

# 相对路径转绝对路径
[[ "$CASE_PATH" = /* ]] || CASE_PATH="$ROOT/$CASE_PATH"

if [ "$MODE" = "cpg" ]; then
  export ICE_LOG_SUFFIX="_cpg"
  SKILL_CMD="/defect-detection-cpg"
else
  export ICE_LOG_SUFFIX=""
  SKILL_CMD="/defect-detection"
fi

cd "$ROOT"
claude --print --dangerously-skip-permissions \
  "$SKILL_CMD 请对以下用例执行完整检测流程：$CASE_PATH"
