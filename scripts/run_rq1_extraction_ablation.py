#!/usr/bin/env python3
"""提取层消融实验脚本。

该脚本用于生成新版论文中的 Pure Rule / Pure LLM / Hybrid 提取层消融结果。
它只在 results/ 下创建新的实验目录，并把原始 Stage 1 产物复制到实验目录后再
执行受限 LLM 补全，避免覆盖 testfiles/MiBench 中已有的正式结果。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from rq1_eval_utils import (
    ARCHS,
    CASES,
    DEFECT_TYPES,
    DIMS,
    MIBENCH,
    eval_irq_mask,
    eval_isr,
    eval_priority,
    eval_shared_access,
    evaluate_rq1,
    load_meta,
    prf,
    resolve_analysis_dir,
)
from run_rq1_holdout_pilot import (
    build_completion_prompt,
    call_llm,
    incremental_merge_interrupts,
    normalize_completion_patch,
    parse_json_response,
    rebuild_shared_variables,
)
from eval_rq1_llm import (
    eval_irq_mask_llm,
    eval_isr_llm,
    eval_priority_llm,
    eval_shared_access_llm,
)


# WSL/Windows 路径大小写可能不同；优先使用当前工作目录，避免 resolve()
# 得到的路径大小写与沙箱 writable root 不一致。
PROJECT_ROOT = Path(os.environ.get("PWD", ".").replace("虚拟C盘", "虚拟c盘")).absolute()
REQUIRED_ANALYSIS_FILES = [
    "functions.json",
    "interrupt_switches.json",
    "interrupt_priorities.json",
    "shared_variables.json",
    "function_call_relations.json",
    "variable_operations.json",
    "global_variables.json",
]
DIM_EVALUATORS = {
    "ISR识别": eval_isr,
    "IRQ Mask": eval_irq_mask,
    "Priority": eval_priority,
    "Shared Access": eval_shared_access,
}
LLM_DIM_EVALUATORS = {
    "ISR识别": eval_isr_llm,
    "IRQ Mask": eval_irq_mask_llm,
    "Priority": eval_priority_llm,
    "Shared Access": eval_shared_access_llm,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RQ1 extraction-layer ablation.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--base-url", default="https://ark.cn-beijing.volces.com/api/coding")
    parser.add_argument("--model", default="minimax-m2.7")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--empty-retries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="Only scan trigger cases, do not call LLM")
    parser.add_argument("--case-tag", action="append", default=None, help="Restrict to explicit case tag(s)")
    return parser.parse_args()


def default_output_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PROJECT_ROOT / "results" / f"rq1_extraction_ablation_ark_{stamp}"


def case_tag(defect_type: str, case_id: str, arch: str) -> str:
    return f"{defect_type}/{case_id}/{arch}"


def iter_cases(case_tags: set[str] | None = None):
    for defect_type in DEFECT_TYPES:
        for case_id in CASES:
            for arch in ARCHS:
                tag = case_tag(defect_type, case_id, arch)
                if case_tags and tag not in case_tags:
                    continue
                case_dir = MIBENCH / defect_type / case_id / arch
                if case_dir.exists():
                    yield defect_type, case_id, arch, case_dir


def dst_analysis_dir(root: Path, defect_type: str, case_id: str, arch: str) -> Path:
    return root / defect_type / case_id / arch / "improved_interrupt_analysis"


def copy_analysis_subset(src: Path, dst: Path) -> None:
    """复制 RQ1/Hybrid 必需的分析产物，避免复制大型 CPG graph artifacts。"""
    dst.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_ANALYSIS_FILES:
        source = src / name
        if source.exists():
            shutil.copy2(source, dst / name)


def evaluate_case_dims(analysis_dir: Path, meta: dict) -> dict[str, tuple[int, int, int]]:
    return {dim: evaluator(analysis_dir, meta) for dim, evaluator in DIM_EVALUATORS.items()}


def should_trigger_completion(results: dict[str, tuple[int, int, int]]) -> list[str]:
    trigger_dims = []
    for dim, (_tp, fp, fn) in results.items():
        if fp > 0 or fn > 0:
            trigger_dims.append(dim)
    return trigger_dims


def build_hybrid_workspace(root: Path, case_tags: set[str] | None = None) -> list[dict]:
    """复制全部待评估 case 的 Stage 1 产物，并记录需要 Hybrid 补全的 case。"""
    triggers = []
    for defect_type, case_id, arch, _case_dir in iter_cases(case_tags):
        meta = load_meta(defect_type, case_id, arch)
        if meta is None:
            continue
        source_analysis = resolve_analysis_dir(defect_type, case_id, arch)
        target_analysis = dst_analysis_dir(root, defect_type, case_id, arch)
        copy_analysis_subset(source_analysis, target_analysis)
        results = evaluate_case_dims(source_analysis, meta)
        trigger_dims = should_trigger_completion(results)
        if trigger_dims:
            triggers.append(
                {
                    "tag": case_tag(defect_type, case_id, arch),
                    "defect_type": defect_type,
                    "case_id": case_id,
                    "arch": arch,
                    "trigger_dims": trigger_dims,
                    "rule_case_results": {
                        dim: {"tp": tp, "fp": fp, "fn": fn}
                        for dim, (tp, fp, fn) in results.items()
                    },
                }
            )
    return triggers


def run_completion_for_trigger(trigger: dict, hybrid_root: Path, empty_retries: int) -> dict:
    defect_type = trigger["defect_type"]
    case_id = trigger["case_id"]
    arch = trigger["arch"]
    case_dir = MIBENCH / defect_type / case_id / arch
    analysis_dir = dst_analysis_dir(hybrid_root, defect_type, case_id, arch)

    started = time.time()
    prompt, prompt_payload, extra_candidates = build_completion_prompt(case_dir, analysis_dir, arch)
    llm_result = call_llm(prompt, empty_retries=empty_retries)
    raw_text = llm_result["text"]
    parsed = parse_json_response(raw_text)

    if parsed.get("empty_response") or parsed.get("parse_error"):
        accepted = []
        validation = {
            "proposed_candidates": 0,
            "accepted_candidates": 0,
            "rejected_candidates": 0,
            "rejected_reasons": ["empty_response" if parsed.get("empty_response") else "json_parse_failure"],
        }
    else:
        accepted, validation = normalize_completion_patch(parsed, analysis_dir, extra_candidates)

    merge_stats = incremental_merge_interrupts(analysis_dir, accepted, extra_candidates)
    rebuilt_shared = rebuild_shared_variables(analysis_dir)

    prompt_payload_summary = dict(prompt_payload)
    source = prompt_payload_summary.pop("source", "")
    prompt_payload_summary["source_chars"] = len(source)
    result = {
        "tag": trigger["tag"],
        "trigger_dims": trigger["trigger_dims"],
        "elapsed_sec": round(time.time() - started, 3),
        "prompt_payload": prompt_payload_summary,
        "raw_response": raw_text,
        "parsed_response": parsed,
        "accepted_interrupts": accepted,
        "extra_candidates": extra_candidates,
        "validation": validation,
        "merge_stats": merge_stats,
        "shared_variables_rebuilt": rebuilt_shared,
        "response_status": llm_result["status"],
        "llm_attempts": llm_result["attempts"],
    }
    (analysis_dir / "rq1_extraction_completion.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def coverage_from_analysis(analysis_root: Path | None) -> dict[str, dict]:
    totals = {dim: {"covered": 0, "total": 0} for dim in DIMS}
    for defect_type, case_id, arch, _case_dir in iter_cases():
        meta = load_meta(defect_type, case_id, arch)
        if meta is None:
            continue
        analysis_dir = resolve_analysis_dir(defect_type, case_id, arch, analysis_root)
        if not analysis_dir.exists():
            continue
        results = evaluate_case_dims(analysis_dir, meta)
        for dim, (tp, fp, fn) in results.items():
            gt_count = tp + fn
            if gt_count == 0:
                continue
            totals[dim]["total"] += 1
            if fn == 0 and fp == 0:
                totals[dim]["covered"] += 1
    for dim, row in totals.items():
        total = row["total"]
        row["coverage"] = round(row["covered"] / total, 4) if total else None
    return totals


def coverage_from_llm_outputs() -> dict[str, dict]:
    totals = {dim: {"covered": 0, "total": 0} for dim in DIMS}
    for defect_type, case_id, arch, case_dir in iter_cases():
        meta = load_meta(defect_type, case_id, arch)
        if meta is None:
            continue
        path = case_dir / "improved_interrupt_analysis" / "rq1_llm_result.json"
        if not path.exists():
            continue
        llm_result = json.loads(path.read_text(encoding="utf-8"))
        results = {dim: evaluator(llm_result, meta) for dim, evaluator in LLM_DIM_EVALUATORS.items()}
        for dim, (tp, fp, fn) in results.items():
            gt_count = tp + fn
            if gt_count == 0:
                continue
            totals[dim]["total"] += 1
            if fn == 0 and fp == 0:
                totals[dim]["covered"] += 1
    for dim, row in totals.items():
        total = row["total"]
        row["coverage"] = round(row["covered"] / total, 4) if total else None
    return totals


def normalize_llm_eval(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    table = data.get("table2_llm", {})
    return {"table2": table, "source": str(path), "llm_calls": 96}


def add_average(table: dict) -> dict:
    metrics = ["precision", "recall", "f1"]
    average = {}
    for metric in metrics:
        average[metric] = round(sum(table[dim][metric] for dim in DIMS) / len(DIMS), 4)
    table["Average"] = average
    return table


def attach_coverage_and_calls(result: dict, coverage: dict, llm_calls: int) -> dict:
    table = {dim: dict(result["table2"][dim]) for dim in DIMS}
    for dim in DIMS:
        table[dim]["coverage"] = coverage[dim]["coverage"]
        table[dim]["covered_cases"] = coverage[dim]["covered"]
        table[dim]["coverage_cases"] = coverage[dim]["total"]
    add_average(table)
    result = dict(result)
    result["table2"] = table
    result["llm_calls"] = llm_calls
    return result


def main() -> None:
    args = parse_args()
    output_root = (args.output_root or default_output_root()).resolve()
    hybrid_root = output_root / "hybrid"
    case_tags = set(args.case_tag) if args.case_tag else None

    os.environ["ANTHROPIC_BASE_URL"] = args.base_url
    os.environ["ANTHROPIC_MODEL"] = args.model

    output_root.mkdir(parents=True, exist_ok=True)
    pure_rule = evaluate_rq1()
    pure_llm = normalize_llm_eval(PROJECT_ROOT / "results" / "rq1_llm.json")
    triggers = build_hybrid_workspace(hybrid_root, case_tags)

    (output_root / "pure_rule_eval.json").write_text(
        json.dumps(pure_rule, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_root / "pure_llm_eval.json").write_text(
        json.dumps(pure_llm, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_root / "trigger_cases.json").write_text(
        json.dumps(triggers, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    completion_outputs = []
    api_started = time.time()
    if not args.dry_run and triggers:
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
            futures = [
                executor.submit(run_completion_for_trigger, trigger, hybrid_root, args.empty_retries)
                for trigger in triggers
            ]
            for future in as_completed(futures):
                completion_outputs.append(future.result())

    api_timing = {
        "base_url": args.base_url,
        "model": args.model,
        "max_tokens": 4096,
        "concurrency": args.concurrency,
        "dry_run": args.dry_run,
        "triggered_cases": len(triggers),
        "completed_calls": len(completion_outputs),
        "wall_sec": round(time.time() - api_started, 3),
        "calls": sorted(completion_outputs, key=lambda item: item["tag"]),
    }
    (output_root / "api_timing.json").write_text(
        json.dumps(api_timing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    hybrid_eval = evaluate_rq1(analysis_root=hybrid_root)
    (output_root / "hybrid_eval.json").write_text(
        json.dumps(hybrid_eval, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "output_root": str(output_root),
        "pure_rule": attach_coverage_and_calls(pure_rule, coverage_from_analysis(None), 0),
        "pure_llm": attach_coverage_and_calls(pure_llm, coverage_from_llm_outputs(), 96),
        "hybrid": attach_coverage_and_calls(hybrid_eval, coverage_from_analysis(hybrid_root), len(completion_outputs)),
        "trigger_cases": triggers,
        "api_timing": api_timing,
    }
    (output_root / "rq1_extraction_ablation.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok",
        "output_root": str(output_root),
        "dry_run": args.dry_run,
        "triggered_cases": len(triggers),
        "completed_calls": len(completion_outputs),
        "hybrid_f1": {dim: summary["hybrid"]["table2"][dim]["f1"] for dim in DIMS},
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
