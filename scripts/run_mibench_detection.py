#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server import (
    build_iacpg,
    build_interrupt_facts,
    iacpg_preemptions,
    iacpg_summary,
    iacpg_switches,
    iacpg_variable,
    interrupt_analyze,
)


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_meta_for_case(case_dir: Path) -> Path | None:
    root = Path(__file__).resolve().parents[1]
    meta_path = (
        root
        / "testfiles"
        / "MIBench"
        / "meta"
        / case_dir.parent.name
        / f"{case_dir.name}.yml"
    )
    return meta_path if meta_path.exists() else None


def run_pipeline(case_dir: Path) -> dict:
    stage1 = interrupt_analyze(str(case_dir), mode="static")
    if stage1.get("status") != "ok":
        raise RuntimeError(f"interrupt_analyze failed: {stage1}")

    facts = build_interrupt_facts(str(case_dir))
    if facts.get("status") != "ok":
        raise RuntimeError(f"build_interrupt_facts failed: {facts}")

    graph = build_iacpg(str(case_dir))
    if graph.get("status") != "ok":
        raise RuntimeError(f"build_iacpg failed: {graph}")

    summary = iacpg_summary(str(case_dir))
    preemptions = iacpg_preemptions(str(case_dir))
    switches = iacpg_switches(str(case_dir))

    return {
        "stage1": stage1,
        "facts": facts,
        "graph": graph,
        "summary": summary,
        "preemptions": preemptions,
        "switches": switches,
    }


def type_to_bits(type_str: str) -> int:
    """Convert C type string to bit width."""
    if not type_str:
        return 0
    type_str = type_str.lower()
    if "64" in type_str or "long long" in type_str:
        return 64
    if "int32" in type_str or "uint32" in type_str or "dword" in type_str:
        return 32
    if (
        "int16" in type_str
        or "uint16" in type_str
        or "short" in type_str
        or "word" in type_str
    ):
        return 16
    if (
        "char" in type_str
        or "int8" in type_str
        or "uint8" in type_str
        or "byte" in type_str
    ):
        return 8
    return 32


def is_multiword_pair(var_name: str, all_vars: list) -> bool:
    """Check if variable is part of a multiword pair (e.g., sec_high + sec_low)."""
    var_lower = var_name.lower()
    if "_high" in var_lower:
        base = var_lower.replace("_high", "")
        low_name = base + "_low"
        return any(v.get("name", "").lower() == low_name for v in all_vars)
    if "_low" in var_lower:
        base = var_lower.replace("_low", "")
        high_name = base + "_high"
        return any(v.get("name", "").lower() == high_name for v in all_vars)
    return False


def detect(case_dir: Path, meta_path: Path | None, pipeline_result: dict) -> dict:
    analysis_dir = case_dir / "improved_interrupt_analysis"
    functions = load_json(
        analysis_dir / "functions.json",
        {"interrupt_functions": [], "main_functions": [], "regular_functions": []},
    )
    ops = load_json(analysis_dir / "variable_operations.json", [])
    rels = load_json(
        analysis_dir / "interrupt_facts" / "interrupt_relations.json",
        {"preemptions": [], "switch_relations": [], "cross_context_accesses": []},
    )
    global_vars = load_json(analysis_dir / "global_variables.json", [])
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) if meta_path else {}
    source_files = sorted(case_dir.glob("*.c"))
    source_text = "\n\n".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in source_files
    )

    if isinstance(global_vars, dict):
        var_type_map = {
            v["name"]: v.get("type", "")
            for v in global_vars.get("global_variables", [])
        }
    elif isinstance(global_vars, list):
        var_type_map = {v["name"]: v.get("type", "") for v in global_vars}
    else:
        var_type_map = {}

    main_names = {f["name"] for f in functions.get("main_functions", [])}
    isr_names = {f["name"] for f in functions.get("interrupt_functions", [])}
    preempt_pairs = {(x["src"], x["dst"]) for x in rels.get("preemptions", [])}
    switch_targets = defaultdict(set)
    for s in rels.get("switch_relations", []):
        switch_targets[s.get("src_function")].add(s.get("target_interrupt"))

    by_var = defaultdict(list)
    for op in ops:
        by_var[op.get("variable")].append(op)

    variable_evidence = {}
    for var, items in by_var.items():
        main_reads = sorted(
            [
                x
                for x in items
                if x.get("function") in main_names and x.get("operation_type") == "read"
            ],
            key=lambda x: x.get("line_number", 0),
        )
        main_writes = sorted(
            [
                x
                for x in items
                if x.get("function") in main_names
                and x.get("operation_type") == "write"
            ],
            key=lambda x: x.get("line_number", 0),
        )
        isr_reads = sorted(
            [
                x
                for x in items
                if x.get("function") in isr_names and x.get("operation_type") == "read"
            ],
            key=lambda x: x.get("line_number", 0),
        )
        isr_writes = sorted(
            [
                x
                for x in items
                if x.get("function") in isr_names and x.get("operation_type") == "write"
            ],
            key=lambda x: x.get("line_number", 0),
        )
        variable_evidence[var] = {
            "main_reads": main_reads,
            "main_writes": main_writes,
            "isr_reads": isr_reads,
            "isr_writes": isr_writes,
        }

    atomic_rows = []
    for var, ev in variable_evidence.items():
        if len(ev["main_reads"]) >= 2 and ev["isr_writes"]:
            op1 = ev["main_reads"][0]
            op2 = ev["isr_writes"][0]
            op3 = ev["main_reads"][1]
            if (op1["function"], op2["function"]) in preempt_pairs:
                atomic_rows.append(
                    {
                        "variable": var,
                        "window": [
                            op1.get("line_number"),
                            op2.get("line_number"),
                            op3.get("line_number"),
                        ],
                        "contexts": [
                            op1.get("function"),
                            op2.get("function"),
                            op3.get("function"),
                        ],
                        "graph_evidence": [
                            "INTERRUPT_PREEMPTS",
                            "ENABLES",
                            "ACCESSES_SHARED_VAR",
                            "POTENTIAL_CONCURRENCY_ON",
                        ],
                        "reason": "主流程存在二次读取，ISR 对同一共享变量有写入，且图中存在可抢占与使能证据。",
                    }
                )
        elif (ev["main_reads"] or ev["main_writes"]) and (
            ev["isr_reads"] or ev["isr_writes"]
        ):
            if ev["isr_writes"] or ev["main_writes"]:
                first_main = (ev["main_reads"] + ev["main_writes"])[0]
                first_isr = (ev["isr_reads"] + ev["isr_writes"])[0]
                if (first_main["function"], first_isr["function"]) in preempt_pairs:
                    atomic_rows.append(
                        {
                            "variable": var,
                            "window": [
                                first_main.get("line_number"),
                                first_isr.get("line_number"),
                                "N/A",
                            ],
                            "contexts": [
                                first_main.get("function"),
                                first_isr.get("function"),
                            ],
                            "graph_evidence": [
                                "INTERRUPT_PREEMPTS",
                                "ACCESSES_SHARED_VAR",
                            ],
                            "reason": "存在并发读写，但缺少稳定观察的第二个主流程读点，保留为 uncertain 候选。",
                            "uncertain": True,
                        }
                    )

    div_zero_hits = []
    array_oob_hits = []
    for var, ev in variable_evidence.items():
        if not ev["isr_writes"]:
            continue
        if re.search(
            rf"if\s*\([^\)]*\b{re.escape(var)}\b\s*!=\s*0[^\)]*\)", source_text
        ) and re.search(rf"[/%]\s*{re.escape(var)}\b", source_text):
            div_zero_hits.append(
                {
                    "variable": var,
                    "graph_evidence": ["INTERRUPT_PREEMPTS", "ACCESSES_SHARED_VAR"],
                    "reason": "发现非零检查和后续除法，且 ISR 可写该共享变量。",
                }
            )
        if re.search(
            rf"if\s*\([^\)]*\b{re.escape(var)}\b\s*<", source_text
        ) and re.search(rf"\[[^\]]*\b{re.escape(var)}\b[^\]]*\]", source_text):
            array_oob_hits.append(
                {
                    "variable": var,
                    "graph_evidence": ["INTERRUPT_PREEMPTS", "ACCESSES_SHARED_VAR"],
                    "reason": "发现边界检查和数组访问，且 ISR 可写该共享变量。",
                }
            )

    mw_race_hits = []
    PLATFORM_BITS = 32
    all_global_vars_list = list(var_type_map.values())
    for var, ev in variable_evidence.items():
        if not ev["isr_writes"] and not ev["main_writes"]:
            continue
        has_isr_access = bool(ev["isr_reads"] or ev["isr_writes"])
        has_main_access = bool(ev["main_reads"] or ev["main_writes"])
        if not (has_isr_access and has_main_access):
            continue
        first_main = (
            (ev["main_reads"] + ev["main_writes"])[0]
            if (ev["main_reads"] or ev["main_writes"])
            else None
        )
        first_isr = (
            (ev["isr_reads"] + ev["isr_writes"])[0]
            if (ev["isr_reads"] or ev["isr_writes"])
            else None
        )
        if first_main and first_isr:
            if (first_main["function"], first_isr["function"]) in preempt_pairs or (
                first_isr["function"],
                first_main["function"],
            ) in preempt_pairs:
                var_bits = type_to_bits(var_type_map.get(var, ""))
                is_multiword = var_bits > PLATFORM_BITS
                is_pair = is_multiword_pair(var, all_global_vars_list)
                if is_multiword or is_pair:
                    mw_race_hits.append(
                        {
                            "variable": var,
                            "type_bits": var_bits,
                            "platform_bits": PLATFORM_BITS,
                            "is_pair": is_pair,
                            "window": [
                                first_main.get("line_number") if first_main else "N/A",
                                first_isr.get("line_number") if first_isr else "N/A",
                                "N/A",
                            ],
                            "contexts": [
                                first_main.get("function") if first_main else "N/A",
                                first_isr.get("function") if first_isr else "N/A",
                            ],
                            "graph_evidence": [
                                "INTERRUPT_PREEMPTS",
                                "ACCESSES_SHARED_VAR",
                            ],
                            "reason": f"变量位宽({var_bits}) > 平台位宽({PLATFORM_BITS})，或存在多字配对模式({'是' if is_pair else '否'})，且存在可抢占并发访问。",
                        }
                    )

    atomic_yes = [x for x in atomic_rows if not x.get("uncertain")]
    atomic_conclusion = "yes" if atomic_yes else ("uncertain" if atomic_rows else "no")
    div_conclusion = "yes" if div_zero_hits else "no"
    array_conclusion = "yes" if array_oob_hits else "no"
    mw_conclusion = "yes" if mw_race_hits else "no"

    hits = []
    if atomic_conclusion == "yes":
        hits.append("atomicity_violation")
    if div_conclusion == "yes":
        hits.append("interrupt_aware_div_zero")
    if array_conclusion == "yes":
        hits.append("interrupt_aware_array_oob")
    if mw_conclusion == "yes":
        hits.append("multiword_data_race")

    if len(hits) > 1:
        overall = "multi-label"
    elif len(hits) == 1:
        overall = "single-label"
    elif "uncertain" in {atomic_conclusion, div_conclusion, array_conclusion}:
        overall = "uncertain"
    else:
        overall = "no_bug"

    variable_queries = {}
    for var in sorted(variable_evidence):
        variable_queries[var] = iacpg_variable(str(case_dir), var)

    expected = meta.get("defect_classes", []) if isinstance(meta, dict) else []
    return {
        "case_path": str(case_dir),
        "meta_path": str(meta_path) if meta_path else None,
        "expected_defect_classes": expected,
        "detected_overall": overall,
        "detected_types": hits,
        "pipeline": pipeline_result,
        "results": {
            "atomicity_violation": {
                "conclusion": atomic_conclusion,
                "candidates": atomic_rows,
            },
            "interrupt_aware_div_zero": {
                "conclusion": div_conclusion,
                "candidates": div_zero_hits,
            },
            "interrupt_aware_array_oob": {
                "conclusion": array_conclusion,
                "candidates": array_oob_hits,
            },
            "multiword_data_race": {
                "conclusion": mw_conclusion,
                "candidates": mw_race_hits,
            },
        },
        "variable_queries": variable_queries,
    }


def render_markdown(result: dict) -> str:
    res = result["results"]

    def row(name: str, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if candidates:
            first = candidates[0]
            variable = first.get("variable", "N/A")
            window = first.get("window", "N/A")
            evidence = ", ".join(first.get("graph_evidence", [])) or "N/A"
        else:
            variable = "N/A"
            window = "N/A"
            evidence = "N/A"
        return f"| {name} | {payload.get('conclusion', 'no')} | {variable} | {window} | {evidence} |"

    lines = [
        f"# Detection Report: {Path(result['case_path']).name}",
        "",
        "## 1) 总结",
        f"- 测试用例：`{result['case_path']}`",
        f"- 检测结论：`{result['detected_overall']}`",
        f"- 命中类型：`{result['detected_types']}`",
        f"- 预期标签（meta）：`{result.get('expected_defect_classes', [])}`",
        "",
        "## 2) 分类结果表",
        "| 缺陷类型 | 结论 | 共享变量 | 三元窗口 (op1, interrupt, op3) | 关键证据 |",
        "|---|---|---|---|---|",
        row("atomicity_violation", res["atomicity_violation"]),
        row("interrupt_aware_div_zero", res["interrupt_aware_div_zero"]),
        row("interrupt_aware_array_oob", res["interrupt_aware_array_oob"]),
        row("multiword_data_race", res["multiword_data_race"]),
        "",
        "## 3) 证据说明",
    ]

    for defect_name, payload in res.items():
        lines.append(f"### {defect_name}")
        lines.append(f"- 结论：`{payload.get('conclusion')}`")
        if payload.get("candidates"):
            for idx, item in enumerate(payload["candidates"], 1):
                lines.append(
                    f"- 候选 {idx}: variable=`{item.get('variable')}`, window=`{item.get('window')}`, reason={item.get('reason')}"
                )
        else:
            lines.append("- 无命中候选。")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_mibench_detection.py <case_dir>")
    case_dir = Path(sys.argv[1]).resolve()
    if not case_dir.exists():
        raise SystemExit(f"case_dir not found: {case_dir}")

    meta_path = find_meta_for_case(case_dir)
    pipeline = run_pipeline(case_dir)
    result = detect(case_dir, meta_path, pipeline)

    out_dir = case_dir / "improved_interrupt_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "detection_result.json"
    md_path = out_dir / "detection_report.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    md_path.write_text(render_markdown(result), encoding="utf-8")

    print(json_path)
    print(md_path)
    print(
        json.dumps(
            {
                "case_path": str(case_dir),
                "detected_overall": result["detected_overall"],
                "detected_types": result["detected_types"],
                "expected_defect_classes": result.get("expected_defect_classes", []),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
