#!/usr/bin/env python3
"""RQ3: 三种配置检测精度对比（Table 4）。

Config 1: Agent + IACPG  → detection_result.json
Config 2: Agent CPG      → detection_result_cpg.json
Config 3: LLM Zero-shot  → detection_result_zeroshot.json

评估方式：
- 正样本（defect_classes 非空）：只检查目录对应的主标签（GT 不穷尽）
- 负样本（defect_classes 为空）：检查全部 4 个标签（GT 穷尽，任何检出均为 FP）

按架构 × 配置分组，计算 P/R/F1。

用法：
  python scripts/eval_rq3.py [--verbose]
"""
import json
import sys
from pathlib import Path

import yaml

from meta_utils import load_meta_checked

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

DEFECT_CLASS_MAP = {
    "AtomicityViolation": "atomicity_violation",
    "BufferOverflow": "interrupt_aware_array_oob",
    "DivideByZero": "interrupt_aware_div_zero",
    "MultiwordDataRace": "multiword_data_race",
}

ALL_DEFECT_CLASSES = list(DEFECT_CLASS_MAP.values())

CONFIGS = {
    "IACPG": "detection_result.json",
    "CPG": "detection_result_cpg.json",
    "ZeroShot": "detection_result_zeroshot.json",
    # NOTE: SpecChecker-Int does not natively distinguish AV from MDR;
    # results are evaluated family-wise against each benchmark subset's label.
    "SpecChecker": "detection_result_specchecker.json",
}


def load_meta(defect_type: str, case_id: str, arch: str) -> dict | None:
    p = MIBENCH / defect_type / "meta" / f"{case_id}_{arch}.yml"
    return load_meta_checked(p, case_id, arch)


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def get_gt_defect_class(defect_type: str) -> str:
    return DEFECT_CLASS_MAP.get(defect_type, "")


def is_detected(result: dict, defect_class: str) -> bool:
    """判断 detection_result 是否检测到指定缺陷类型。"""
    if not result:
        return False
    # 新 schema: hit_types
    if defect_class in result.get("hit_types", []):
        return True
    # 新 schema: results[defect_class].conclusion == "yes"
    results = result.get("results", {})
    if defect_class in results:
        return results[defect_class].get("conclusion", "no") == "yes"
    # CPG schema 变体：defects[] 或 detections[] 数组
    for key in ("defects", "detections"):
        for d in result.get(key, []):
            if not isinstance(d, dict):
                continue
            dtype = (d.get("type") or d.get("defect_type") or "").lower().replace(" ", "_").replace("-", "_")
            if dtype == defect_class or dtype.replace("_", "") == defect_class.replace("_", ""):
                if d.get("detected") or d.get("confirmed"):
                    return True
    return False


def main():
    verbose = "--verbose" in sys.argv
    out_path = None
    if "--output" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--output") + 1])

    # stats[config][arch] = [tp, fp, fn]
    stats = {cfg: {arch: [0, 0, 0] for arch in ARCHS + ["all"]} for cfg in CONFIGS}

    for dt in DEFECT_TYPES:
        gt_class = get_gt_defect_class(dt)
        for case_id in CASES:
            for arch in ARCHS:
                meta = load_meta(dt, case_id, arch)
                if meta is None:
                    continue
                analysis_dir = MIBENCH / dt / case_id / arch / "improved_interrupt_analysis"

                # ground truth: check meta defect_classes
                gt_classes = set(meta.get("defect_classes", []))
                has_defect = gt_class in gt_classes
                is_negative = len(gt_classes) == 0

                for cfg_name, result_file in CONFIGS.items():
                    result = load_json(analysis_dir / result_file)

                    if is_negative:
                        # 负样本：检查全部 4 个标签，任何检出均为 FP
                        for dc in ALL_DEFECT_CLASSES:
                            if is_detected(result, dc):
                                stats[cfg_name][arch][1] += 1   # FP
                                stats[cfg_name]["all"][1] += 1
                    else:
                        # 正样本：只检查主标签
                        detected = is_detected(result, gt_class)
                        if has_defect:
                            if detected:
                                stats[cfg_name][arch][0] += 1   # TP
                                stats[cfg_name]["all"][0] += 1
                            else:
                                stats[cfg_name][arch][2] += 1   # FN
                                stats[cfg_name]["all"][2] += 1

                    if verbose:
                        if is_negative:
                            fp_labels = [dc for dc in ALL_DEFECT_CLASSES if is_detected(result, dc)]
                            tag = f"FP({','.join(fp_labels)})" if fp_labels else "TN"
                        else:
                            detected = is_detected(result, gt_class)
                            tag = "TP" if detected else "FN"
                        print(f"  {cfg_name} {dt}/{case_id}/{arch}: {tag} (result={'found' if result else 'missing'})")

    print("\n=== RQ3: Table 4 ===")
    print(f"{'配置':<12} {'架构':<8} {'TP':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
    print("-" * 60)
    table = {}
    for cfg_name in CONFIGS:
        table[cfg_name] = {}
        for arch in ARCHS + ["all"]:
            tp, fp, fn = stats[cfg_name][arch]
            p, r, f1 = prf(tp, fp, fn)
            label = arch if arch != "all" else "ALL"
            print(f"{cfg_name:<12} {label:<8} {tp:>5} {fp:>5} {fn:>5} {p:>7.3f} {r:>7.3f} {f1:>7.3f}")
            table[cfg_name][arch] = {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
        print()

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"table4": table}, indent=2, ensure_ascii=False))
        print(f"结果已写入 {out_path}")


if __name__ == "__main__":
    main()
