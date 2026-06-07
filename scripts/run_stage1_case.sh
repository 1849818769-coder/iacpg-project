#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE_NO="${1:-1}"

cd "$ROOT"

python_cmd=$(cat <<'PY'
import sys, yaml, pathlib
p = pathlib.Path('tests/test_config.yml')
obj = yaml.safe_load(p.read_text(encoding='utf-8'))
obj['project']['number'] = int(sys.argv[1])
p.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(f"set project.number={sys.argv[1]}")
PY
)

scripts/conda_run.sh python -c "$python_cmd" "$CASE_NO"
scripts/conda_run.sh python tests/test_stage1.py
