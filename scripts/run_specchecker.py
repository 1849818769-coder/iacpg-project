#!/usr/bin/env python3
"""阶段 B：批量运行 SpecChecker-Int，对全部 96 个用例产出 detection_result_specchecker.json。

前提：已用 validate_specchecker.py 在 4 个代表性 case 上确认 flag 语法和输出解析正确。

用法（Windows PowerShell）：
  # 全量运行
  python scripts/run_specchecker.py

  # 只跑特定缺陷类型
  python scripts/run_specchecker.py --defect-type BufferOverflow

  # 只跑特定架构
  python scripts/run_specchecker.py --arch arm

  # 只跑特定 case
  python scripts/run_specchecker.py --defect-type AtomicityViolation --case simple_001

  # dry-run：只打印命令，不执行
  python scripts/run_specchecker.py --dry-run

  # 跳过已有结果（断点续跑）
  python scripts/run_specchecker.py --skip-existing

注意：必须在 Windows 环境下运行（SpecChecker-Int.exe 是 Windows 原生程序）。

NOTE: SpecChecker-Int does not natively distinguish atomicity violations from
multi-word data races; we evaluate its conflict-detection capability against
the family label of each benchmark subset (family-wise mapping).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 复用 validate_specchecker 中的核心函数
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_specchecker import (
    BIN_DIR,
    CLANG_EXE,
    DEFECT_FLAG_MAP,
    SPECCHECKER_EXE,
    run_case,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"

DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

OUTPUT_FILENAME = "detection_result_specchecker.json"


def main():
    parser = argparse.ArgumentParser(description="SpecChecker-Int 批量运行脚本（阶段 B）")
    parser.add_argument("--defect-type", choices=DEFECT_TYPES,
                        help="只运行指定缺陷类型")
    parser.add_argument("--arch", choices=ARCHS,
                        help="只运行指定架构")
    parser.add_argument("--case",
                        help="只运行指定 case（如 simple_001）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印命令，不执行")
    parser.add_argument("--skip-existing", action="store_true",
                        help="跳过已有 detection_result_specchecker.json 的用例")
    parser.add_argument("--flag-style", choices=["bare", "equals"], default="bare",
                        help="flag 语法：bare=-int-bof，equals=-int-bof=true")
    args = parser.parse_args()

    # 检查工具是否存在
    if not args.dry_run:
        for exe in [CLANG_EXE, SPECCHECKER_EXE]:
            if not exe.exists():
                print(f"ERROR: 找不到工具: {exe}", file=sys.stderr)
                print("请确认在 Windows 环境下运行，且 SpecChecker-Int-main/bin/ 目录完整。",
                      file=sys.stderr)
                sys.exit(1)

    defect_types = [args.defect_type] if args.defect_type else DEFECT_TYPES
    archs = [args.arch] if args.arch else ARCHS
    cases = [args.case] if args.case else CASES

    total = 0
    skipped = 0
    success = 0
    hit = 0
    errors = 0

    for dt in defect_types:
        if dt not in DEFECT_FLAG_MAP:
            print(f"WARN: {dt} 不在 DEFECT_FLAG_MAP 中，跳过")
            continue
        for case_id in cases:
            for arch in archs:
                case_dir = MIBENCH / dt / case_id / arch
                if not case_dir.exists():
                    continue

                total += 1
                out_file = case_dir / "improved_interrupt_analysis" / OUTPUT_FILENAME

                if args.skip_existing and out_file.exists():
                    skipped += 1
                    print(f"[SKIP] {dt}/{case_id}/{arch} (已存在)")
                    continue

                print(f"\n{'='*60}")
                print(f"[{total}] {dt}/{case_id}/{arch}")

                result = run_case(case_dir, dry_run=args.dry_run, flag_style=args.flag_style)

                if args.dry_run:
                    continue

                # 写出结果
                out_dir = case_dir / "improved_interrupt_analysis"
                out_dir.mkdir(parents=True, exist_ok=True)
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                status = result.get("status", "unknown")
                if status == "success":
                    success += 1
                    if result.get("hit_types"):
                        hit += 1
                        print(f"  → HIT: {result['hit_types']}")
                    else:
                        print(f"  → no bug detected")
                elif status == "timeout":
                    errors += 1
                    print(f"  → TIMEOUT")
                else:
                    errors += 1
                    print(f"  → ERROR: {result.get('error', '')}")

    if not args.dry_run:
        print(f"\n{'='*60}")
        print(f"完成！总计: {total}，跳过: {skipped}，成功: {success}，命中: {hit}，错误/超时: {errors}")
        print(f"结果文件: <case_dir>/improved_interrupt_analysis/{OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
