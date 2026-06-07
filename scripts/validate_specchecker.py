#!/usr/bin/env python3
"""阶段 A：单例验证脚本 — 验证 SpecChecker-Int 能在一个用例上正确运行。

用法（Windows PowerShell）：
  python scripts/validate_specchecker.py --case testfiles/MiBench/BufferOverflow/simple_001/arm
  python scripts/validate_specchecker.py --case testfiles/MiBench/BufferOverflow/simple_001/arm --dry-run

注意：必须在 Windows 环境下运行（SpecChecker-Int.exe 是 Windows 原生程序）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = PROJECT_ROOT / "SpecChecker-Int-main" / "bin"
CLANG_EXE = BIN_DIR / "clang.exe"
SPECCHECKER_EXE = BIN_DIR / "SpecChecker-Int.exe"

# Minimal stdint.h stub — covers all types actually used in our MiBench test cases.
# Injected into a temp dir and passed via -I to clang, because SpecChecker-Int's
# bundled clang does not ship standard C headers.
_STDINT_STUB = textwrap.dedent("""\
    #ifndef _STDINT_H
    #define _STDINT_H
    typedef signed   char      int8_t;
    typedef signed   short     int16_t;
    typedef signed   int       int32_t;
    typedef signed   long long int64_t;
    typedef unsigned char      uint8_t;
    typedef unsigned short     uint16_t;
    typedef unsigned int       uint32_t;
    typedef unsigned long long uint64_t;
    typedef int8_t   int_least8_t;
    typedef int16_t  int_least16_t;
    typedef int32_t  int_least32_t;
    typedef int64_t  int_least64_t;
    typedef uint8_t  uint_least8_t;
    typedef uint16_t uint_least16_t;
    typedef uint32_t uint_least32_t;
    typedef uint64_t uint_least64_t;
    typedef int32_t  intptr_t;
    typedef uint32_t uintptr_t;
    typedef int64_t  intmax_t;
    typedef uint64_t uintmax_t;
    #endif
""")

DEFECT_FLAG_MAP = {
    "BufferOverflow":      ("-int-bof",                   "interrupt_aware_array_oob"),
    "DivideByZero":        ("-int-dbz",                   "interrupt_aware_div_zero"),
    "AtomicityViolation":  ("-int-data-access-conflict",  "atomicity_violation"),
    "MultiwordDataRace":   ("-int-data-access-conflict",  "multiword_data_race"),
}

# 检测输出中各类型的关键词
BUG_KEYWORDS = {
    "-int-bof":                  ["Buffer_Over_Flow", "BOF", "int-bof", "buffer over flow"],
    "-int-dbz":                  ["Divide_By_Zero", "DBZ", "int-dbz", "divide by zero"],
    "-int-data-access-conflict": ["Data_Access_Conflict", "data access conflict"],
}


def find_c_file(case_dir: Path) -> Path | None:
    """找到 case 目录下的 .c 源文件。"""
    c_files = list(case_dir.glob("*.c"))
    if not c_files:
        return None
    return sorted(c_files)[0]


def load_functions_json(case_dir: Path) -> dict:
    """从 improved_interrupt_analysis/functions.json 读取函数信息。"""
    p = case_dir / "improved_interrupt_analysis" / "functions.json"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_meta(case_dir: Path) -> dict:
    """推断并加载 meta YAML 文件。

    case_dir 形如 testfiles/MiBench/<DefectType>/simple_00X/<arch>/
    meta 在 testfiles/MiBench/<DefectType>/meta/simple_00X_<arch>.yml
    """
    parts = case_dir.resolve().parts
    # 找到 MiBench 在路径中的位置
    try:
        mibench_idx = next(i for i, p in enumerate(parts) if p == "MiBench")
    except StopIteration:
        return {}
    defect_type = parts[mibench_idx + 1]
    case_id = parts[mibench_idx + 2]
    arch = parts[mibench_idx + 3]
    meta_path = Path(*parts[: mibench_idx + 2]) / "meta" / f"{case_id}_{arch}.yml"
    if not meta_path.exists():
        return {}
    with open(meta_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_tasks_and_priorities(case_dir: Path) -> tuple[list[str], list[int]]:
    """从 functions.json 和 meta YAML 提取 tasks 和 priority 列表。

    Returns:
        tasks:      [main_func, isr1, isr2, ...]
        priorities: [0, p1, p2, ...]  (main=0, ISR 优先从 meta 读)
    """
    funcs = load_functions_json(case_dir)
    meta = load_meta(case_dir)

    # main 函数名
    main_funcs = funcs.get("main_functions", [])
    if not main_funcs:
        raise ValueError(f"functions.json 中没有 main_functions: {case_dir}")
    main_name = main_funcs[0]["name"]

    # ISR 函数名列表
    isr_funcs = [f["name"] for f in funcs.get("interrupt_functions", [])]

    # priority：优先从 meta 读
    meta_handlers = (meta.get("interrupts") or {}).get("handlers", []) or []
    meta_priority_map: dict[str, int] = {}
    for h in meta_handlers:
        name = h.get("name")
        prio = h.get("priority")
        if name and prio is not None:
            meta_priority_map[name] = int(prio)

    tasks = [main_name] + isr_funcs
    priorities: list[int] = [0]  # main=0
    for idx, isr in enumerate(isr_funcs, start=1):
        if isr in meta_priority_map:
            priorities.append(meta_priority_map[isr])
        else:
            priorities.append(idx)  # fallback: 按出现顺序

    return tasks, priorities


def get_defect_type(case_dir: Path) -> str:
    """从路径中推断 DefectType。"""
    parts = case_dir.resolve().parts
    try:
        mibench_idx = next(i for i, p in enumerate(parts) if p == "MiBench")
        return parts[mibench_idx + 1]
    except StopIteration:
        raise ValueError(f"无法从路径推断 DefectType: {case_dir}")


def detect_hit(flag: str, output: str, report_path: Path) -> tuple[bool, int]:
    """解析工具输出，判断是否命中。

    返回 (has_hit, bug_count)。
    先尝试解析 reportFile JSON，再 fallback 到 console 关键词匹配。
    """
    # 1. 尝试解析 reportFile
    if report_path.exists():
        try:
            with open(report_path, encoding="utf-8", errors="ignore") as f:
                report = json.load(f)
            if isinstance(report, list) and len(report) > 0:
                return True, len(report)
            if isinstance(report, dict):
                bugs = report.get("bugs") or report.get("Bugs") or []
                if bugs:
                    return True, len(bugs)
        except Exception:
            pass

    # 2. fallback：关键词匹配 console 输出
    keywords = BUG_KEYWORDS.get(flag, [])
    output_lower = output.lower()
    for kw in keywords:
        if kw.lower() in output_lower:
            return True, 1

    return False, 0


def run_case(case_dir: Path, dry_run: bool = False, flag_style: str = "bare") -> dict:
    """对单个用例运行 SpecChecker-Int。

    flag_style:
      "bare"   → -int-bof
      "equals" → -int-bof=true
    """
    c_file = find_c_file(case_dir)
    if c_file is None:
        return {"status": "error", "error": "找不到 .c 文件", "hit_types": []}

    defect_type = get_defect_type(case_dir)
    if defect_type not in DEFECT_FLAG_MAP:
        return {"status": "error", "error": f"未知 DefectType: {defect_type}", "hit_types": []}

    flag_base, hit_type = DEFECT_FLAG_MAP[defect_type]
    flag = flag_base if flag_style == "bare" else f"{flag_base}=true"

    try:
        tasks, priorities = extract_tasks_and_priorities(case_dir)
    except Exception as e:
        return {"status": "error", "error": str(e), "hit_types": []}

    tasks_str = ",".join(tasks)
    priority_str = ",".join(str(p) for p in priorities)

    with tempfile.TemporaryDirectory() as tmpdir:
        bc_file = Path(tmpdir) / (c_file.stem + ".bc")
        report_file = Path(tmpdir) / (c_file.stem + ".report.json")

        # 写入 stdint.h stub，解决 SpecChecker-Int 自带 clang 缺少标准头文件的问题
        stub_dir = Path(tmpdir) / "stub_include"
        stub_dir.mkdir()
        (stub_dir / "stdint.h").write_text(_STDINT_STUB, encoding="utf-8")

        # AV 用例包含 #include "../../common.h"，但该相对路径解析到
        # AtomicityViolation/common.h（不存在），真正的 common.h 在 MiBench/ 根下。
        # 解决方案：把源文件内容读出，将有问题的 #include 替换为 common.h 实际内容，
        # 写到临时目录下编译，不修改原始文件。
        common_h_src = PROJECT_ROOT / "testfiles" / "MiBench" / "common.h"
        src_text = c_file.read_text(encoding="utf-8", errors="ignore")
        if common_h_src.exists() and '../../common.h' in src_text:
            common_h_text = common_h_src.read_text(encoding="utf-8")
            # 内联 common.h 同时在文件最头部注入 stdint stub，确保 int64_t 等类型可用
            src_text = src_text.replace(
                '#include "../../common.h"',
                f'/* stdint stub inlined */\n{_STDINT_STUB}\n/* common.h inlined */\n{common_h_text}\n'
            )
            patched_c = Path(tmpdir) / c_file.name
            patched_c.write_text(src_text, encoding="utf-8")
            compile_target = patched_c
        else:
            compile_target = c_file

        # --- Step 1: clang 编译 ---
        clang_cmd = [
            str(CLANG_EXE),
            "-O0", "-g", "-emit-llvm", "-c",
            f"-I{stub_dir}",
            str(compile_target),
            "-o", str(bc_file),
        ]
        print(f"\n[CLANG] {' '.join(clang_cmd)}")
        if dry_run:
            print(f"[dry-run] stub_include/ 写入 stdint.h")
            print("[dry-run] 跳过执行")
            return {"status": "dry-run", "hit_types": [], "tasks": tasks_str, "priority": priority_str}

        try:
            r = subprocess.run(
                clang_cmd,
                cwd=str(BIN_DIR),
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="ignore",
            )
            if r.returncode != 0:
                return {
                    "status": "error",
                    "error": f"clang failed (rc={r.returncode}): {r.stderr[:300]}",
                    "hit_types": [],
                }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "clang timeout", "hit_types": []}

        # --- Step 2: SpecChecker-Int ---
        sc_cmd = [
            str(SPECCHECKER_EXE),
            str(bc_file),
            flag,
            f"-tasks={tasks_str}",
            f"-priority={priority_str}",
            f"-reportFile={report_file}",
            "-human-readable",
            "-detailReportInfo",
        ]
        print(f"[SPECCHECKER] {' '.join(sc_cmd)}")
        try:
            r2 = subprocess.run(
                sc_cmd,
                cwd=str(BIN_DIR),
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="ignore",
            )
            raw_output = (r2.stdout or "") + (r2.stderr or "")
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "SpecChecker-Int timeout", "hit_types": [],
                    "tasks": tasks_str, "priority": priority_str}

        has_hit, bug_count = detect_hit(flag_base, raw_output, report_file)

        return {
            "hit_types": [hit_type] if has_hit else [],
            "tool": "SpecChecker-Int",
            "specchecker_flag": flag,
            "tasks": tasks_str,
            "priority": priority_str,
            "raw_bugs": bug_count,
            "status": "success",
            "report_file": str(report_file),
            "raw_output": raw_output[:2000],  # 截断避免过大
        }


def main():
    parser = argparse.ArgumentParser(description="SpecChecker-Int 单例验证脚本（阶段 A）")
    parser.add_argument("--case", required=True,
                        help="用例目录，如 testfiles/MiBench/BufferOverflow/simple_001/arm")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印命令，不执行")
    parser.add_argument("--flag-style", choices=["bare", "equals"], default="bare",
                        help="flag 语法：bare=-int-bof，equals=-int-bof=true")
    args = parser.parse_args()

    case_dir = Path(args.case)
    if not case_dir.is_absolute():
        case_dir = PROJECT_ROOT / case_dir
    case_dir = case_dir.resolve()

    if not case_dir.exists():
        print(f"ERROR: 目录不存在: {case_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"=== 验证用例: {case_dir} ===")
    print(f"    flag-style: {args.flag_style}")

    # 检查工具是否存在
    if not args.dry_run:
        for exe in [CLANG_EXE, SPECCHECKER_EXE]:
            if not exe.exists():
                print(f"ERROR: 找不到工具: {exe}", file=sys.stderr)
                sys.exit(1)

    result = run_case(case_dir, dry_run=args.dry_run, flag_style=args.flag_style)

    print("\n--- 结果 ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("hit_types"):
        print(f"\n✓ 命中: {result['hit_types']}")
    elif result.get("status") == "success":
        print("\n✗ 未命中（无 bug 报告）")


if __name__ == "__main__":
    main()
