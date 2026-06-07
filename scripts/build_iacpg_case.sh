#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE_NO="${1:-1}"
CASE_DIR=$(printf "%s/testfiles/2.1_remarks/svp_simple_%03d" "$ROOT" "$CASE_NO")

cd "$ROOT"
source scripts/joern_env.sh >/dev/null
scripts/run_stage1_case.sh "$CASE_NO"
scripts/conda_run.sh python scripts/build_interrupt_facts.py "$CASE_DIR"
scripts/conda_run.sh python scripts/build_iacpg.py "$CASE_DIR"
GRAPH="$CASE_DIR/improved_interrupt_analysis/iacpg_artifacts/iacpg.graphml"
echo "Built: $GRAPH"
scripts/conda_run.sh python scripts/query_iacpg.py "$GRAPH" summary
