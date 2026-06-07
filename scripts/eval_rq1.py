#!/usr/bin/env python3
"""RQ1: 静态分析语义提取精度评估（Table 2）。

对比 improved_interrupt_analysis/ 提取结果与 meta YAML ground truth，
计算 ISR识别 / IRQ Mask / Priority / Shared Access 四个维度的 P/R/F1。

用法：
  python scripts/eval_rq1.py [--analysis-root PATH] [--arch msp430] [--verbose]
"""
import argparse
import json
from pathlib import Path

from rq1_eval_utils import DIMS, evaluate_rq1


def main():
    parser = argparse.ArgumentParser(description="Evaluate RQ1 semantic extraction metrics.")
    parser.add_argument("--analysis-root", type=Path, default=None, help="Alternate root that mirrors <DefectType>/<case>/<arch>/improved_interrupt_analysis")
    parser.add_argument("--arch", dest="archs", action="append", help="Restrict evaluation to one or more architectures")
    parser.add_argument("--case", dest="cases", action="append", help="Restrict evaluation to one or more case ids")
    parser.add_argument("--defect-type", dest="defect_types", action="append", help="Restrict evaluation to one or more defect types")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate_rq1(
        analysis_root=args.analysis_root,
        defect_types=args.defect_types,
        case_ids=args.cases,
        archs=args.archs,
        verbose=args.verbose,
    )

    print("\n=== RQ1: Table 2 ===")
    print(f"{'维度':<16} {'TP':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
    print("-" * 60)
    for dim in DIMS:
        row = result["table2"][dim]
        print(
            f"{dim:<16} {row['tp']:>5} {row['fp']:>5} {row['fn']:>5} "
            f"{row['precision']:>7.3f} {row['recall']:>7.3f} {row['f1']:>7.3f}"
        )
    if result["missing"]:
        print(f"\n(跳过 {result['missing']} 个缺失 meta YAML 的用例)")
    if args.analysis_root:
        print(f"\nanalysis_root = {args.analysis_root}")
    if result["analyzed_cases"]:
        print(f"evaluated_cases = {result['analyzed_cases']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n结果已写入 {args.output}")


if __name__ == "__main__":
    main()
