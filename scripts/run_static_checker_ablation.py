#!/usr/bin/env python3
"""在隔离副本上运行 IACPG + 纯静态缺陷判断消融。

该脚本用于生成可选的 verifier ablation 结果：
1. 将 MiBench 用例复制到 results/iacpg_static_checker_*；
2. 复用已有 IACPG 分析产物，4 个 callback-style case 使用 hybrid Stage1 产物；
3. 在隔离目录中运行纯规则判断并计算 RQ3 风格指标。

脚本不写回 testfiles/MiBench，也不覆盖 results/rq*.json。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

from mcp_server import build_interrupt_facts


PROJECT_ROOT = Path(os.environ.get("PWD", Path(__file__).resolve().parents[1]).replace("虚拟C盘", "虚拟c盘")).absolute()
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
HYBRID_ROOT = PROJECT_ROOT / "results" / "rq1_extraction_ablation_ark_20260516_135113" / "hybrid"

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
HYBRID_PATCH_CASES = {
    ("MultiwordDataRace", "simple_005", "arm"),
    ("MultiwordDataRace", "simple_005", "avr"),
    ("MultiwordDataRace", "simple_005", "msp430"),
    ("MultiwordDataRace", "simple_005", "riscv"),
}
PLATFORM_BITS = {"arm": 32, "riscv": 32, "avr": 8, "msp430": 16}


def default_output_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PROJECT_ROOT / "results" / f"iacpg_static_checker_{stamp}"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def type_to_bits(type_str: str) -> int:
    """把常见 C 类型字符串映射到位宽，用于多字长判断。"""
    if not type_str:
        return 0
    text = type_str.lower()
    if "64" in text or "long long" in text:
        return 64
    if "32" in text or "long" in text:
        return 32
    if "16" in text or "short" in text:
        return 16
    if "8" in text or "char" in text:
        return 8
    return 32


def copy_case(defect_type: str, case_id: str, arch: str, output_root: Path) -> Path:
    """复制单个用例到隔离目录，并替换需要 hybrid 修复的 Stage1 产物。"""
    src = MIBENCH / defect_type / case_id / arch
    dst = output_root / "cases" / defect_type / case_id / arch
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("claude_run_*.log", "tool_call_log*.jsonl"))

    if (defect_type, case_id, arch) in HYBRID_PATCH_CASES:
        hybrid_analysis = HYBRID_ROOT / defect_type / case_id / arch / "improved_interrupt_analysis"
        dst_analysis = dst / "improved_interrupt_analysis"
        if not hybrid_analysis.exists():
            raise FileNotFoundError(f"hybrid analysis not found: {hybrid_analysis}")
        if dst_analysis.exists():
            shutil.rmtree(dst_analysis)
        shutil.copytree(hybrid_analysis, dst_analysis)
        facts = build_interrupt_facts(str(dst))
        if facts.get("status") != "ok":
            raise RuntimeError(f"build_interrupt_facts failed for {dst}: {facts}")
    return dst


def collect_cases(limit: int | None, smoke: bool) -> list[tuple[str, str, str]]:
    """收集待运行 case。smoke 模式四类缺陷各取一个 arm case。"""
    if smoke:
        return [
            ("AtomicityViolation", "simple_001", "arm"),
            ("BufferOverflow", "simple_001", "arm"),
            ("DivideByZero", "simple_001", "arm"),
            ("MultiwordDataRace", "simple_001", "arm"),
        ]
    cases = [(dt, cid, arch) for dt in DEFECT_TYPES for cid in CASES for arch in ARCHS]
    return cases[:limit] if limit else cases


def meta_for(defect_type: str, case_id: str, arch: str) -> dict:
    path = MIBENCH / defect_type / "meta" / f"{case_id}_{arch}.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def source_text(case_dir: Path) -> str:
    return "\n\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in sorted(case_dir.glob("*.c")))


def is_multiword_pair(var_name: str, all_names: set[str]) -> bool:
    """识别 high/low 形式的多字配对变量。"""
    name = var_name.lower()
    if name.endswith("_high"):
        return name[:-5] + "_low" in all_names
    if name.endswith("_low"):
        return name[:-4] + "_high" in all_names
    return False


def detect_static(case_dir: Path, arch: str, meta: dict) -> dict:
    """基于已有 IACPG 分析产物执行纯规则缺陷判断。"""
    analysis = case_dir / "improved_interrupt_analysis"
    functions = load_json(analysis / "functions.json", {"interrupt_functions": [], "main_functions": []})
    ops = load_json(analysis / "variable_operations.json", [])
    rels = load_json(analysis / "interrupt_facts" / "interrupt_relations.json", {"preemptions": []})
    globals_payload = load_json(analysis / "global_variables.json", [])
    text = source_text(case_dir)

    globals_list = globals_payload.get("global_variables", []) if isinstance(globals_payload, dict) else globals_payload
    var_type = {item.get("name"): item.get("type", "") for item in globals_list if isinstance(item, dict)}
    global_names = {name.lower() for name in var_type}
    main_names = {item.get("name") for item in functions.get("main_functions", [])}
    isr_names = {item.get("name") for item in functions.get("interrupt_functions", [])}
    preempt_pairs = {(item.get("src"), item.get("dst")) for item in rels.get("preemptions", []) if isinstance(item, dict)}

    by_var: dict[str, list[dict]] = defaultdict(list)
    for op in ops:
        if isinstance(op, dict) and op.get("variable"):
            by_var[op["variable"]].append(op)

    hits: list[str] = []
    details = {}
    platform_bits = PLATFORM_BITS[arch]

    atomic_candidates = []
    dbz_candidates = []
    oob_candidates = []
    mdr_candidates = []

    for var, items in by_var.items():
        main_access = [x for x in items if x.get("function") in main_names]
        isr_access = [x for x in items if x.get("function") in isr_names]
        main_reads = [x for x in main_access if x.get("operation_type") == "read"]
        isr_writes = [x for x in isr_access if x.get("operation_type") == "write"]
        if not main_access or not isr_access:
            continue

        first_main = sorted(main_access, key=lambda x: x.get("line_number", 0))[0]
        first_isr = sorted(isr_access, key=lambda x: x.get("line_number", 0))[0]
        has_preempt = (first_main.get("function"), first_isr.get("function")) in preempt_pairs
        if not has_preempt:
            continue

        if len(main_reads) >= 2 and isr_writes:
            atomic_candidates.append({"variable": var, "reason": "R-W-R with ISR write and preemption evidence"})

        if isr_writes and re.search(rf"if\s*\([^\)]*\b{re.escape(var)}\b\s*!=\s*0[^\)]*\)", text) and re.search(rf"[/%]\s*{re.escape(var)}\b", text):
            dbz_candidates.append({"variable": var, "reason": "check-then-divide with ISR write"})

        if isr_writes and re.search(rf"if\s*\([^\)]*\b{re.escape(var)}\b\s*<", text) and re.search(rf"\[[^\]]*\b{re.escape(var)}\b[^\]]*\]", text):
            oob_candidates.append({"variable": var, "reason": "check-then-index with ISR write"})

        var_bits = type_to_bits(var_type.get(var, ""))
        if (var_bits > platform_bits or is_multiword_pair(var, global_names)) and (isr_writes or any(x.get("operation_type") == "write" for x in main_access)):
            mdr_candidates.append(
                {
                    "variable": var,
                    "type_bits": var_bits,
                    "platform_bits": platform_bits,
                    "reason": "multiword variable accessed across preemptible contexts",
                }
            )

    if atomic_candidates:
        hits.append("atomicity_violation")
    if dbz_candidates:
        hits.append("interrupt_aware_div_zero")
    if oob_candidates:
        hits.append("interrupt_aware_array_oob")
    if mdr_candidates:
        hits.append("multiword_data_race")

    details["atomicity_violation"] = {"conclusion": "yes" if atomic_candidates else "no", "candidates": atomic_candidates}
    details["interrupt_aware_div_zero"] = {"conclusion": "yes" if dbz_candidates else "no", "candidates": dbz_candidates}
    details["interrupt_aware_array_oob"] = {"conclusion": "yes" if oob_candidates else "no", "candidates": oob_candidates}
    details["multiword_data_race"] = {"conclusion": "yes" if mdr_candidates else "no", "candidates": mdr_candidates}

    return {
        "case_path": str(case_dir),
        "expected_defect_classes": meta.get("defect_classes", []),
        "hit_types": hits,
        "verdict": "multi-label" if len(hits) > 1 else ("single-label" if hits else "no_bug"),
        "results": details,
    }


def is_detected(result: dict, defect_class: str) -> bool:
    return defect_class in result.get("hit_types", [])


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def evaluate(rows: list[dict]) -> dict:
    """按 RQ3 主标签口径评估静态 checker 输出。"""
    stats = {arch: [0, 0, 0] for arch in ARCHS + ["all"]}
    for row in rows:
        meta = row["meta"]
        result = row["result"]
        defect_type = row["defect_type"]
        arch = row["arch"]
        gt_class = DEFECT_CLASS_MAP[defect_type]
        gt_classes = set(meta.get("defect_classes", []))
        if not gt_classes:
            for dc in ALL_DEFECT_CLASSES:
                if is_detected(result, dc):
                    stats[arch][1] += 1
                    stats["all"][1] += 1
        else:
            detected = is_detected(result, gt_class)
            if detected:
                stats[arch][0] += 1
                stats["all"][0] += 1
            else:
                stats[arch][2] += 1
                stats["all"][2] += 1

    metrics = {}
    for arch, (tp, fp, fn) in stats.items():
        p, r, f1 = prf(tp, fp, fn)
        metrics[arch] = {"TP": tp, "FP": fp, "FN": fn, "P": round(p, 4), "R": round(r, 4), "F1": round(f1, 4)}
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated IACPG + static checker ablation.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    output_root = (args.output_root or default_output_root()).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cases = collect_cases(args.limit, args.smoke)
    rows = []
    for defect_type, case_id, arch in cases:
        case_dir = copy_case(defect_type, case_id, arch, output_root)
        meta = meta_for(defect_type, case_id, arch)
        result = detect_static(case_dir, arch, meta)
        out_dir = case_dir / "improved_interrupt_analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "detection_result_static.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rows.append(
            {
                "defect_type": defect_type,
                "case_id": case_id,
                "arch": arch,
                "case_dir": str(case_dir),
                "meta": meta,
                "result": result,
            }
        )

    summary = {
        "output_root": str(output_root),
        "mode": "smoke" if args.smoke else "full_or_limited",
        "case_count": len(rows),
        "metrics": evaluate(rows),
        "cases": [
            {
                "tag": f"{row['defect_type']}/{row['case_id']}/{row['arch']}",
                "hit_types": row["result"]["hit_types"],
                "expected": row["meta"].get("defect_classes", []),
            }
            for row in rows
        ],
    }
    (output_root / "static_checker_rq3_eval.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "README.md").write_text(
        "# IACPG Static Checker Ablation\n\n"
        "All cases are isolated copies under this results directory. Original MiBench data and results/rq*.json are not modified.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
