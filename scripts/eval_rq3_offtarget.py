#!/usr/bin/env python3
"""RQ3 辅助分析：label-set agreement 与 off-target overprediction 统计。

补充主表（eval_rq3.py 按主标签评估）无法体现的多标签质量差异。

指标：
- label_set_agreement: 预测标签集合与 meta.defect_classes 一致的比例
- off_target_positive_cases: 在正样本用例中存在额外预测标签的用例数
- off_target_positive_labels: 在正样本用例中的额外预测标签总数
- control_fp_cases / control_fp_labels: 在负样本控制组（defect_classes=[]）上的误报统计
- missing_results: 缺失结果文件的用例数

说明：
- 该脚本不替代 eval_rq3.py 的主表，只用于补充分析 overprediction 与标签集合一致性。
- 由于当前 meta.defect_classes 不是穷尽多标签标注，label_set_agreement 更适合作为
  “与标注标签集合的一致性”指标，而不应直接宣称为严格多标签准确率。

用法：
  python scripts/eval_rq3_offtarget.py [--verbose] [--output results/rq3_offtarget.json]
"""

import json
import sys
from pathlib import Path

from meta_utils import load_meta_checked

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

ALL_DEFECT_CLASSES = [
    "atomicity_violation",
    "interrupt_aware_array_oob",
    "interrupt_aware_div_zero",
    "multiword_data_race",
]

CONFIGS = {
    "IACPG": "detection_result.json",
    "CPG": "detection_result_cpg.json",
    "ZeroShot": "detection_result_zeroshot.json",
}


def load_meta(defect_type: str, case_id: str, arch: str):
    path = MIBENCH / defect_type / "meta" / f"{case_id}_{arch}.yml"
    return load_meta_checked(path, case_id, arch)


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_detected_set(result: dict | None) -> set[str]:
    """从 detection_result 中提取所有被判为 yes 的缺陷类型集合。

    与 eval_rq3.py 的 is_detected() 保持同样的兼容思路：
    - hit_types
    - results[dc].conclusion == "yes"
    - defects[] / detections[] 变体
    """
    if not result:
        return set()

    detected: set[str] = set()

    for hit_type in result.get("hit_types", []):
        if hit_type in ALL_DEFECT_CLASSES:
            detected.add(hit_type)

    results = result.get("results", {})
    for defect_class in ALL_DEFECT_CLASSES:
        entry = results.get(defect_class, {})
        if isinstance(entry, dict) and entry.get("conclusion") == "yes":
            detected.add(defect_class)
        elif entry == "yes":
            detected.add(defect_class)

    for key in ("defects", "detections"):
        for item in result.get(key, []):
            if not isinstance(item, dict):
                continue
            dtype = (item.get("type") or item.get("defect_type") or "").lower()
            dtype = dtype.replace(" ", "_").replace("-", "_")
            for defect_class in ALL_DEFECT_CLASSES:
                if dtype == defect_class or dtype.replace("_", "") == defect_class.replace("_", ""):
                    if item.get("detected") or item.get("confirmed"):
                        detected.add(defect_class)

    return detected


def main():
    verbose = "--verbose" in sys.argv
    out_path = None
    if "--output" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--output") + 1])

    summary = {}

    for cfg_name, result_file in CONFIGS.items():
        total_cases = 0
        available_results = 0
        missing_results = 0
        label_set_agreement = 0

        positive_total = 0
        off_target_positive_cases = 0
        off_target_positive_labels = 0

        control_total = 0
        control_fp_cases = 0
        control_fp_labels = 0

        details = []

        for defect_type in DEFECT_TYPES:
            for case_id in CASES:
                for arch in ARCHS:
                    meta = load_meta(defect_type, case_id, arch)
                    if meta is None:
                        continue

                    total_cases += 1
                    analysis_dir = MIBENCH / defect_type / case_id / arch / "improved_interrupt_analysis"
                    result = load_json(analysis_dir / result_file)
                    if result is None:
                        missing_results += 1
                        if verbose:
                            details.append(f"  {defect_type}/{case_id}/{arch}: missing result")
                        continue

                    available_results += 1
                    gt_set = set(meta.get("defect_classes", []))
                    det_set = get_detected_set(result)

                    if det_set == gt_set:
                        label_set_agreement += 1

                    extra = det_set - gt_set
                    missing = gt_set - det_set

                    if gt_set:
                        positive_total += 1
                        if extra:
                            off_target_positive_cases += 1
                            off_target_positive_labels += len(extra)
                    else:
                        control_total += 1
                        if det_set:
                            control_fp_cases += 1
                            control_fp_labels += len(det_set)

                    if verbose and (extra or missing):
                        details.append(
                            f"  {defect_type}/{case_id}/{arch}: "
                            f"gt={sorted(gt_set)} det={sorted(det_set)} "
                            f"extra={sorted(extra)} missing={sorted(missing)}"
                        )

        result_row = {
            "total_cases": total_cases,
            "available_results": available_results,
            "missing_results": missing_results,
            "label_set_agreement": label_set_agreement,
            "label_set_agreement_pct": round(label_set_agreement / available_results * 100, 1) if available_results else 0.0,
            "positive_total": positive_total,
            "off_target_positive_cases": off_target_positive_cases,
            "off_target_positive_labels": off_target_positive_labels,
            "control_total": control_total,
            "control_fp_cases": control_fp_cases,
            "control_fp_labels": control_fp_labels,
        }
        summary[cfg_name] = result_row

        print(f"\n=== {cfg_name} ===")
        print(
            f"  label-set agreement: {label_set_agreement} / {available_results}"
            f" = {result_row['label_set_agreement_pct']:.1f}%"
        )
        print(
            f"  off-target (positive cases): {off_target_positive_cases} / {positive_total} cases, "
            f"{off_target_positive_labels} extra labels"
        )
        print(
            f"  negative-control FP:        {control_fp_cases} / {control_total} cases, "
            f"{control_fp_labels} extra labels"
        )
        print(f"  missing results:            {missing_results}")
        if verbose and details:
            print("  details:")
            for detail in details:
                print(detail)

    print("\n=== Summary ===")
    print(
        f"{'Config':<12} {'Agreement':>18} {'Off-target(Pos)':>18} "
        f"{'Control FP':>14} {'Missing':>10}"
    )
    print("-" * 82)
    for cfg_name in CONFIGS:
        row = summary[cfg_name]
        agreement = f"{row['label_set_agreement']}/{row['available_results']} ({row['label_set_agreement_pct']:.1f}%)"
        off_target = f"{row['off_target_positive_cases']}/{row['positive_total']}"
        control_fp = f"{row['control_fp_cases']}/{row['control_total']}"
        print(
            f"{cfg_name:<12} {agreement:>18} {off_target:>18} "
            f"{control_fp:>14} {row['missing_results']:>10}"
        )

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"offtarget": summary}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n结果已写入 {out_path}")


if __name__ == "__main__":
    main()
