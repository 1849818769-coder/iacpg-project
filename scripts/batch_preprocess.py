#!/usr/bin/env python3
"""批量预处理：对所有 MIBench 测试用例执行 Stage 1-3（中断语义提取 → 事实构建 → IACPG 构建）。

预跑完成后，智能体只需从 Stage 4 开始查询，大幅加速实验。

用法：
  bash scripts/with_local_env.sh python scripts/batch_preprocess.py [--force]
"""
import json
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server import interrupt_analyze, build_interrupt_facts, build_iacpg

MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]


def iter_cases():
    """遍历所有 <defect_type>/simple_XXX/<arch> 目录。"""
    for dt in DEFECT_TYPES:
        dt_dir = MIBENCH / dt
        if not dt_dir.is_dir():
            continue
        for case_dir in sorted(dt_dir.iterdir()):
            if not case_dir.is_dir() or case_dir.name == "meta":
                continue
            for arch in ARCHS:
                arch_dir = case_dir / arch
                if arch_dir.is_dir():
                    yield arch_dir


def run_stage123(case_dir: Path, force: bool = False) -> dict:
    analysis = case_dir / "improved_interrupt_analysis"
    result = {"case": str(case_dir), "stages": {}}

    # Stage 1
    if not force and (analysis / "functions.json").exists():
        result["stages"]["stage1"] = "skipped"
    else:
        r = interrupt_analyze(str(case_dir), mode="static")
        result["stages"]["stage1"] = "ok" if r.get("status") == "ok" else r

    # Stage 2
    if not force and (analysis / "interrupt_facts" / "interrupt_facts.json").exists():
        result["stages"]["stage2"] = "skipped"
    else:
        r = build_interrupt_facts(str(case_dir))
        result["stages"]["stage2"] = "ok" if r.get("status") == "ok" else r

    # Stage 3
    if not force and (analysis / "iacpg_artifacts" / "iacpg.graphml").exists():
        result["stages"]["stage3"] = "skipped"
    else:
        r = build_iacpg(str(case_dir))
        result["stages"]["stage3"] = "ok" if r.get("status") == "ok" else r

    return result


def main():
    force = "--force" in sys.argv
    cases = list(iter_cases())
    print(f"Found {len(cases)} cases, force={force}")

    ok, fail, skip = 0, 0, 0
    errors = []
    for i, case_dir in enumerate(cases, 1):
        tag = f"[{i}/{len(cases)}] {case_dir.relative_to(MIBENCH)}"
        try:
            r = run_stage123(case_dir, force=force)
            stages = r["stages"]
            if all(v == "skipped" for v in stages.values()):
                skip += 1
                print(f"  {tag} ... all skipped")
            elif all(v in ("ok", "skipped") for v in stages.values()):
                ok += 1
                print(f"  {tag} ... ok ({stages})")
            else:
                fail += 1
                errors.append(r)
                print(f"  {tag} ... FAIL ({stages})")
        except Exception as e:
            fail += 1
            errors.append({"case": str(case_dir), "error": str(e)})
            print(f"  {tag} ... ERROR: {e}")
            traceback.print_exc()

    print(f"\nDone: {ok} ok, {skip} skipped, {fail} failed (total {len(cases)})")
    if errors:
        print("\nErrors:")
        print(json.dumps(errors, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
