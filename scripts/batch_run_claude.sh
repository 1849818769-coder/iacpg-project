#!/usr/bin/env bash
# 批量对实验用例跑 Config 1 (IACPG) 或 Config 2 (CPG)
# 用法:
#   bash scripts/batch_run_claude.sh          # Config 1
#   bash scripts/batch_run_claude.sh cpg      # Config 2
#   CASE_TIMEOUT_SECS=1800 bash scripts/batch_run_claude.sh cpg AtomicityViolation
#
# 进度输出：先统计实际存在的用例目录数为 total_cases；每个用例一行
#   [########------------------]  28% (18/64) RUN  Defect/simple_001/arm
# “#” 已处理进度，“-” 剩余；RUN/SKIP/OK/FAIL/TIMEO 表示该步状态（单次 claude 运行仍可能很慢，条只反映批次进度）。

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-iacpg}"
ONLY="${2:-}"   # 可选：只跑某个缺陷类型，如 AtomicityViolation
MIBENCH="$ROOT/testfiles/MiBench"
DEFECT_TYPES="AtomicityViolation BufferOverflow DivideByZero MultiwordDataRace"
[ -n "$ONLY" ] && DEFECT_TYPES="$ONLY"
CASES="simple_001 simple_002 simple_003 simple_004 simple_005 simple_006"
ARCHS="arm avr msp430 riscv"
CASE_TIMEOUT_SECS="${CASE_TIMEOUT_SECS:-1200}"
TIMEOUT_BIN="$(command -v timeout || true)"

if [ "$MODE" = "cpg" ]; then
  RESULT_FILE="detection_result_cpg.json"
  RUN_LOG_FILE="claude_run_cpg.log"
else
  RESULT_FILE="detection_result.json"
  RUN_LOG_FILE="claude_run_iacpg.log"
fi

if [[ ! "$CASE_TIMEOUT_SECS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: CASE_TIMEOUT_SECS must be a non-negative integer, got '$CASE_TIMEOUT_SECS'" >&2
  exit 1
fi

if [ "$CASE_TIMEOUT_SECS" -gt 0 ] && [ -z "$TIMEOUT_BIN" ]; then
  echo "WARN: timeout command not found; per-case timeout disabled" >&2
fi

cleanup_mcp_joern() {
  local killed=0
  local pids=""
  local joern_pids=""
  local uid=""

  if command -v pgrep >/dev/null 2>&1; then
    uid="$(id -u)"
    pids="$(pgrep -u "$uid" -f "$ROOT/mcp_server.py" 2>/dev/null || true)"
    joern_pids="$(pgrep -u "$uid" -f 'joern.*--server|io\\.joern\\..*server' 2>/dev/null || true)"
  fi

  if [ -n "$pids" ]; then
    echo "Cleanup: stopping MCP servers ($pids)"
    kill $pids 2>/dev/null || true
    killed=1
  fi

  if [ -n "$joern_pids" ]; then
    echo "Cleanup: stopping Joern servers ($joern_pids)"
    kill $joern_pids 2>/dev/null || true
    killed=1
  fi

  if [ "$killed" -eq 1 ]; then
    sleep 2
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
    [ -n "$joern_pids" ] && kill -9 $joern_pids 2>/dev/null || true
  fi
}

trap cleanup_mcp_joern EXIT INT TERM

# 简易进度条：仅统计实际存在的用例目录（与下方循环的 continue 条件一致）
count_total_cases() {
  local n=0
  local dt case_id arch case_path
  for dt in $DEFECT_TYPES; do
    for case_id in $CASES; do
      for arch in $ARCHS; do
        case_path="$MIBENCH/$dt/$case_id/$arch"
        [ -d "$case_path" ] || continue
        n=$((n + 1))
      done
    done
  done
  printf '%s\n' "$n"
}

print_progress_line() {
  local cur="$1" total="$2" status="$3" tag="$4"
  local width=28
  if [ "$total" -le 0 ]; then
    printf '[%s] %s  (?/?) %s\n' "????????????????????????????" "$status" "$tag"
    return
  fi
  local pct=$((100 * cur / total))
  local filled=$((cur * width / total))
  [ "$cur" -gt 0 ] && [ "$filled" -eq 0 ] && filled=1
  local empty=$((width - filled))
  local bar=""
  [ "$filled" -gt 0 ] && bar="${bar}$(printf '%*s' "$filled" '' | tr ' ' '#')"
  [ "$empty" -gt 0 ] && bar="${bar}$(printf '%*s' "$empty" '' | tr ' ' '-')"
  printf '[%s] %3d%% (%2d/%2d) %-5s %s\n' "$bar" "$pct" "$cur" "$total" "$status" "$tag"
}

run_case_with_log() {
  local case_path="$1"
  local mode="$2"
  local tag="$3"
  local log_file="$4"
  local status=0
  local now

  now="$(date '+%F %T')"
  {
    echo "[$now] START mode=$mode case=$tag"
    echo "[$now] LOG=$log_file"
  } > "$log_file"

  if [ "$CASE_TIMEOUT_SECS" -gt 0 ] && [ -n "$TIMEOUT_BIN" ]; then
    if "$TIMEOUT_BIN" --foreground --signal=TERM --kill-after=30s "${CASE_TIMEOUT_SECS}s" \
      bash "$ROOT/scripts/run_case_claude.sh" "$case_path" "$mode" >> "$log_file" 2>&1; then
      status=0
    else
      status=$?
    fi
  else
    if bash "$ROOT/scripts/run_case_claude.sh" "$case_path" "$mode" >> "$log_file" 2>&1; then
      status=0
    else
      status=$?
    fi
  fi

  now="$(date '+%F %T')"
  if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
    echo "[$now] TIMEOUT after ${CASE_TIMEOUT_SECS}s" >> "$log_file"
  else
    echo "[$now] EXIT status=$status" >> "$log_file"
  fi

  return "$status"
}

TOTAL="$(count_total_cases)"
cleanup_mcp_joern
echo "Batch: mode=$MODE  result=$RESULT_FILE  total_cases=$TOTAL"
if [ "$CASE_TIMEOUT_SECS" -gt 0 ] && [ -n "$TIMEOUT_BIN" ]; then
  echo "Timeout: ${CASE_TIMEOUT_SECS}s per case"
else
  echo "Timeout: disabled"
fi
echo ""

ok=0; skip=0; fail=0; timeout_fail=0
idx=0

for dt in $DEFECT_TYPES; do
  for case_id in $CASES; do
    for arch in $ARCHS; do
      case_path="$MIBENCH/$dt/$case_id/$arch"
      [ -d "$case_path" ] || continue

      idx=$((idx + 1))
      tag="$dt/$case_id/$arch"

      result="$case_path/improved_interrupt_analysis/$RESULT_FILE"
      if [ -f "$result" ]; then
        print_progress_line "$idx" "$TOTAL" "SKIP" "$tag"
        echo "  SKIP $tag"
        skip=$((skip + 1))
        continue
      fi

      print_progress_line "$idx" "$TOTAL" "RUN " "$tag"
      echo "  RUN  $tag ..."
      log_file="$case_path/improved_interrupt_analysis/$RUN_LOG_FILE"
      mkdir -p "$case_path/improved_interrupt_analysis"
      if run_case_with_log "$case_path" "$MODE" "$tag" "$log_file"; then
        ok=$((ok + 1))
        print_progress_line "$idx" "$TOTAL" "OK  " "$tag"
      else
        status=$?
        if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
          echo "  TIMEOUT $tag after ${CASE_TIMEOUT_SECS}s (see $log_file)" >&2
          timeout_fail=$((timeout_fail + 1))
          print_progress_line "$idx" "$TOTAL" "TIMEO" "$tag"
        else
          echo "  FAIL $tag (see $log_file)" >&2
          fail=$((fail + 1))
          print_progress_line "$idx" "$TOTAL" "FAIL" "$tag"
        fi
      fi
    done
  done
done

echo ""
echo "Done: $ok ok, $skip skipped, $fail failed, $timeout_fail timed out"
