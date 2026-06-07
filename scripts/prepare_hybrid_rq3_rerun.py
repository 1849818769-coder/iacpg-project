#!/usr/bin/env python3
"""准备并汇总 RQ3 hybrid 补跑工作区。

该脚本只在 results/ 下创建隔离目录：
1. 复制触发 restricted completion 的 4 个源码用例；
2. 把 RQ1 extraction ablation 中已修正的 Stage1 产物复制到隔离用例；
3. 可在 ClaudeCode 跑完后汇总 detection_result.json。

脚本不会写回 testfiles/MiBench，也不会覆盖 results/rq*.json。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PWD", Path(__file__).resolve().parents[1]).replace("虚拟C盘", "虚拟c盘")).absolute()
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFAULT_HYBRID_ROOT = (
    PROJECT_ROOT / "results" / "rq1_extraction_ablation_ark_20260516_135113" / "hybrid"
)
DEFAULT_CASES = [
    ("MultiwordDataRace", "simple_005", "arm"),
    ("MultiwordDataRace", "simple_005", "avr"),
    ("MultiwordDataRace", "simple_005", "msp430"),
    ("MultiwordDataRace", "simple_005", "riscv"),
]


def default_output_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PROJECT_ROOT / "results" / f"rq3_hybrid_claude_rerun_{stamp}"


def resolve_under_project(path: Path) -> Path:
    """把相对路径固定解析到项目根目录，避免 WSL 路径大小写导致只读。"""
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def copy_case_source(src_case: Path, dst_case: Path) -> None:
    """复制用例源码和本地头文件，跳过已有分析产物。"""
    dst_case.mkdir(parents=True, exist_ok=True)
    for item in src_case.iterdir():
        if item.name == "improved_interrupt_analysis":
            continue
        dst = dst_case / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)


def prepare_workspace(output_root: Path, hybrid_root: Path) -> list[dict]:
    """构造隔离 workspace，并返回每个 case 的 manifest 项。"""
    entries: list[dict] = []
    for defect_type, case_id, arch in DEFAULT_CASES:
        source_case = MIBENCH / defect_type / case_id / arch
        hybrid_analysis = hybrid_root / defect_type / case_id / arch / "improved_interrupt_analysis"
        isolated_case = output_root / "cases" / defect_type / case_id / arch
        isolated_analysis = isolated_case / "improved_interrupt_analysis"

        if not source_case.exists():
            raise FileNotFoundError(f"source case not found: {source_case}")
        if not hybrid_analysis.exists():
            raise FileNotFoundError(f"hybrid analysis not found: {hybrid_analysis}")

        copy_case_source(source_case, isolated_case)
        if isolated_analysis.exists():
            shutil.rmtree(isolated_analysis)
        shutil.copytree(hybrid_analysis, isolated_analysis)

        entries.append(
            {
                "tag": f"{defect_type}/{case_id}/{arch}",
                "source_case": str(source_case),
                "hybrid_analysis": str(hybrid_analysis),
                "isolated_case": str(isolated_case),
                "result_file": str(isolated_analysis / "detection_result.json"),
            }
        )
    return entries


def summarize(output_root: Path, entries: list[dict]) -> dict:
    """读取 ClaudeCode 跑完后的结果并生成主标签摘要。"""
    rows = []
    for entry in entries:
        result_path = Path(entry["result_file"])
        payload = None
        hit_types: list[str] = []
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            hit_types = payload.get("hit_types") or payload.get("detected_types") or []
        rows.append(
            {
                "tag": entry["tag"],
                "result_exists": result_path.exists(),
                "hit_types": hit_types,
                "main_hit": "multiword_data_race" in hit_types,
                "off_target": [x for x in hit_types if x != "multiword_data_race"],
            }
        )
    summary = {
        "output_root": str(output_root),
        "cases": rows,
        "all_results_exist": all(row["result_exists"] for row in rows),
        "all_main_hit": all(row["main_hit"] for row in rows),
        "off_target_cases": [row for row in rows if row["off_target"]],
    }
    (output_root / "case_results_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def write_readme(output_root: Path, entries: list[dict]) -> None:
    """写入实验来源和运行命令，方便后续审计。"""
    commands = [
        f"bash scripts/run_case_claude.sh {entry['isolated_case']}"
        for entry in entries
    ]
    text = [
        "# RQ3 Hybrid Claude Rerun",
        "",
        "This directory contains isolated reruns for the four callback-style cases that triggered restricted completion.",
        "Original MiBench cases and results/rq*.json are not modified.",
        "",
        "## Commands",
        "",
        *[f"- `{cmd}`" for cmd in commands],
        "",
        "## Cases",
        "",
        *[f"- `{entry['tag']}` -> `{entry['isolated_case']}`" for entry in entries],
        "",
    ]
    (output_root / "README.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare/summarize isolated RQ3 hybrid rerun workspace.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--hybrid-root", type=Path, default=DEFAULT_HYBRID_ROOT)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()

    output_root = resolve_under_project(args.output_root) if args.output_root else default_output_root()
    manifest_path = output_root / "manifest.json"

    if args.summarize_only:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))["cases"]
        summary = summarize(output_root, entries)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    output_root.mkdir(parents=True, exist_ok=True)
    entries = prepare_workspace(output_root, args.hybrid_root.resolve())
    manifest = {
        "output_root": str(output_root),
        "hybrid_root": str(args.hybrid_root.resolve()),
        "cases": entries,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(output_root, entries)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
