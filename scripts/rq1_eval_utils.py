#!/usr/bin/env python3
"""Shared evaluation helpers for RQ1-style semantic extraction metrics."""

from __future__ import annotations

import json
from pathlib import Path

from meta_utils import load_meta_checked

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]
DIMS = ["ISR识别", "IRQ Mask", "Priority", "Shared Access"]


def load_meta(defect_type: str, case_id: str, arch: str) -> dict | None:
    path = MIBENCH / defect_type / "meta" / f"{case_id}_{arch}.yml"
    return load_meta_checked(path, case_id, arch)


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def eval_isr(analysis_dir: Path, meta: dict) -> tuple[int, int, int]:
    """ISR识别：functions.json interrupt_functions vs meta handlers."""
    funcs = load_json(analysis_dir / "functions.json")
    gt_names = {h["name"] for h in meta.get("interrupts", {}).get("handlers", [])}
    if not funcs or not gt_names:
        return 0, 0, len(gt_names)
    pred_names = {f["name"] for f in funcs.get("interrupt_functions", [])}
    tp = len(pred_names & gt_names)
    fp = len(pred_names - gt_names)
    fn = len(gt_names - pred_names)
    return tp, fp, fn


def _normalize_target(target: str) -> str:
    return "" if target in ("", "global") else target


def eval_irq_mask(analysis_dir: Path, meta: dict) -> tuple[int, int, int]:
    """IRQ Mask: interrupt_switches.json vs meta switches."""
    switches = load_json(analysis_dir / "interrupt_switches.json")
    gt = meta.get("interrupts", {}).get("switches", [])
    gt_set = {(s["op"], _normalize_target(s.get("target", ""))) for s in gt}
    if not switches:
        return 0, 0, len(gt_set)
    pred_set = set()
    for switch in switches:
        op = switch.get("operation", switch.get("op", ""))
        target = _normalize_target(switch.get("target", switch.get("irq", "")))
        pred_set.add((op, target))
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    return tp, fp, fn


def eval_priority(analysis_dir: Path, meta: dict) -> tuple[int, int, int]:
    """Priority: interrupt_priorities.json vs meta handlers[].priority."""
    priorities = load_json(analysis_dir / "interrupt_priorities.json")
    gt_handlers = meta.get("interrupts", {}).get("handlers", [])
    gt_set = {(h["name"], h.get("priority", 0)) for h in gt_handlers if "priority" in h}
    if not priorities or not gt_set:
        return 0, 0, len(gt_set)
    pred_set = set()
    entries = priorities.values() if isinstance(priorities, dict) else priorities
    for entry in entries:
        name = entry.get("function_name", entry.get("function", entry.get("name", "")))
        priority = entry.get("priority", 0)
        pred_set.add((name, priority))
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    return tp, fp, fn


def eval_shared_access(analysis_dir: Path, meta: dict) -> tuple[int, int, int]:
    """Shared Access: shared_variables.json vs meta defects[].variable."""
    shared = load_json(analysis_dir / "shared_variables.json")
    gt_vars = {d["variable"] for d in meta.get("defects", [])}
    if not shared or not gt_vars:
        return 0, 0, len(gt_vars)
    pred_vars = set()
    for entry in shared:
        name = entry.get("name", entry.get("variable", ""))
        if name:
            pred_vars.add(name)
    tp = len(pred_vars & gt_vars)
    fp = 0  # 多提取的共享变量不算误报
    fn = len(gt_vars - pred_vars)
    return tp, fp, fn


def iter_case_keys(
    defect_types: list[str] | None = None,
    case_ids: list[str] | None = None,
    archs: list[str] | None = None,
):
    defect_types = defect_types or DEFECT_TYPES
    case_ids = case_ids or CASES
    archs = archs or ARCHS
    for defect_type in defect_types:
        for case_id in case_ids:
            for arch in archs:
                yield defect_type, case_id, arch


def resolve_analysis_dir(
    defect_type: str,
    case_id: str,
    arch: str,
    analysis_root: Path | None = None,
) -> Path:
    if analysis_root is None:
        return MIBENCH / defect_type / case_id / arch / "improved_interrupt_analysis"
    return analysis_root / defect_type / case_id / arch / "improved_interrupt_analysis"


def evaluate_rq1(
    analysis_root: Path | None = None,
    defect_types: list[str] | None = None,
    case_ids: list[str] | None = None,
    archs: list[str] | None = None,
    verbose: bool = False,
) -> dict:
    totals = {dim: [0, 0, 0] for dim in DIMS}
    missing = 0
    analyzed_cases = 0

    for defect_type, case_id, arch in iter_case_keys(defect_types, case_ids, archs):
        meta = load_meta(defect_type, case_id, arch)
        if meta is None:
            missing += 1
            continue

        analysis_dir = resolve_analysis_dir(defect_type, case_id, arch, analysis_root)
        if not analysis_dir.exists():
            if verbose:
                print(f"  SKIP (no analysis): {defect_type}/{case_id}/{arch}")
            continue

        analyzed_cases += 1
        results = {
            "ISR识别": eval_isr(analysis_dir, meta),
            "IRQ Mask": eval_irq_mask(analysis_dir, meta),
            "Priority": eval_priority(analysis_dir, meta),
            "Shared Access": eval_shared_access(analysis_dir, meta),
        }
        for dim, (tp, fp, fn) in results.items():
            totals[dim][0] += tp
            totals[dim][1] += fp
            totals[dim][2] += fn
        if verbose:
            print(f"  {defect_type}/{case_id}/{arch}: {results}")

    table = {}
    for dim in DIMS:
        tp, fp, fn = totals[dim]
        precision, recall, f1 = prf(tp, fp, fn)
        table[dim] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return {
        "table2": table,
        "missing": missing,
        "analyzed_cases": analyzed_cases,
        "analysis_root": str(analysis_root) if analysis_root else None,
        "defect_types": defect_types or DEFECT_TYPES,
        "case_ids": case_ids or CASES,
        "archs": archs or ARCHS,
    }
