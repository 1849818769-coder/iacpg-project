#!/usr/bin/env python3
"""RQ2: CPG vs IACPG 工具效率对比（Table 3）。

从 tool_call_log.jsonl 读取工具调用记录，计算：
  - 返回数据量 (Chars)         — 在线查询阶段
  - 响应时间 (ms)             — 端到端总时间（含预处理/建图）
  - 推理跳数 (Hops)           — 在线查询阶段
  - 证据完整度 (EC%)          — 在线查询阶段
  - 信噪比 (SNR%)             — 在线查询阶段

用法：
  python scripts/eval_rq2.py [--verbose]
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

# 这些工具不计入在线查询类指标（chars / hops / snr / ec），
# 但仍计入端到端时间 ms。
PREPROCESS_TOOLS = {
    "interrupt_analyze",
    "interrupt_analyze_merge",
    "build_interrupt_facts",
    "build_iacpg",
    "joern_import",
}

# EC三要素：IACPG边类型关键词（精确匹配）
EC_ISR_EDGES    = {"INTERRUPT_PREEMPTS"}
EC_SHARED_EDGES = {"ACCESSES_SHARED_VAR"}
EC_WINDOW_EDGES = {"ENABLES", "DISABLES", "POTENTIAL_CONCURRENCY_ON"}

# EC三要素：CPG文本模式（小写子串匹配）
EC_ISR_TEXT    = {"irqhandler", "_vect", "_isr", "identified as isr", "interrupt handler"}
EC_SHARED_TEXT = {"appears in both", "read at", "written at"}
EC_WINDOW_TEXT = {"no cli", "no critical section", "unprotected", "enables interrupt", "sei()",
                  "preempt", "toctou", "check-then-use", "no disable", "no __disable"}


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return lines


def backup_analysis_dir(defect_type: str, case_id: str, arch: str) -> Path:
    return (
        PROJECT_ROOT
        / "results"
        / "cpg_backups"
        / defect_type
        / case_id
        / arch
        / "improved_interrupt_analysis"
    )


def load_json_with_backup(
    analysis_dir: Path,
    filename: str,
    defect_type: str,
    case_id: str,
    arch: str,
    backup_filename: str | None = None,
):
    primary = analysis_dir / filename
    if primary.exists():
        return load_json(primary)
    if backup_filename:
        backup = backup_analysis_dir(defect_type, case_id, arch) / backup_filename
        if backup.exists():
            return load_json(backup)
    return None


def load_jsonl_with_backup(
    analysis_dir: Path,
    filename: str,
    defect_type: str,
    case_id: str,
    arch: str,
    backup_filename: str | None = None,
) -> list[dict]:
    primary = analysis_dir / filename
    if primary.exists():
        return load_jsonl(primary)
    if backup_filename:
        backup = backup_analysis_dir(defect_type, case_id, arch) / backup_filename
        if backup.exists():
            return load_jsonl(backup)
    return []


def _collect_graph_evidence(result: dict) -> list[str]:
    """从 detection_result 中收集所有 graph_evidence 条目（两种配置通用）。"""
    items = []
    defects = result.get("results") or result.get("defects", {})
    entries = defects.values() if isinstance(defects, dict) else (defects if isinstance(defects, list) else [])
    for info in entries:
        if isinstance(info, dict):
            items.extend(info.get("graph_evidence", []))
    return items


def snr(log: list[dict], result: dict) -> float:
    """信噪比 = 最终报告中 graph_evidence 的字符数 / 所有工具调用返回的总字符数。

    分子：detection_result 中所有 graph_evidence 条目的字符总长（最终有效信号）
    分母：tool_call_log 中所有工具返回的字符总数（原始查询噪音+信号之和）
    两种配置使用相同公式，差异体现在分子/分母比值上。
    """
    total = sum(e.get("result_chars", 0) for e in log)
    if total == 0:
        return 0.0
    evidence = _collect_graph_evidence(result) if result else []
    signal = sum(len(e) for e in evidence)
    return signal / total * 100


def evidence_complete(result: dict) -> bool:
    """证据完整度：检测报告是否覆盖三要素。

    要素1 ISR识别：报告中能指出具体 ISR 函数
    要素2 共享变量：报告中能指出变量在 main 和 ISR 中均有访问
    要素3 并发窗口：报告中能指出存在无保护窗口或中断使能状态

    对 IACPG：从 graph_evidence 中精确匹配 IACPG 边类型关键词
    对 CPG：从 graph_evidence 中做小写子串匹配
    两者共用同一函数，自动适配。
    """
    if not result:
        return False
    evidence = _collect_graph_evidence(result)
    if not evidence:
        return False

    found_isr = found_shared = found_window = False
    for e in evidence:
        e_lower = e.lower()
        # 要素1：ISR识别
        if any(k in e for k in EC_ISR_EDGES) or any(k in e_lower for k in EC_ISR_TEXT):
            found_isr = True
        # 要素2：共享变量
        if any(k in e for k in EC_SHARED_EDGES) or any(k in e_lower for k in EC_SHARED_TEXT):
            found_shared = True
        # 要素3：并发窗口
        if any(k in e for k in EC_WINDOW_EDGES) or any(k in e_lower for k in EC_WINDOW_TEXT):
            found_window = True

    return found_isr and found_shared and found_window


def collect_metrics(
    analysis_dir: Path,
    defect_type: str,
    case_id: str,
    arch: str,
    result_file: str = "detection_result.json",
    log_file: str = "tool_call_log.jsonl",
    backup_result_file: str | None = None,
    backup_log_file: str | None = None,
) -> dict | None:
    full_log = load_jsonl_with_backup(
        analysis_dir, log_file, defect_type, case_id, arch, backup_log_file
    )
    online_log = [e for e in full_log if e.get("tool") not in PREPROCESS_TOOLS]
    result = load_json_with_backup(
        analysis_dir, result_file, defect_type, case_id, arch, backup_result_file
    )
    if not full_log and result is None:
        return None

    total_chars = sum(e.get("result_chars", 0) for e in online_log)
    total_ms = sum(e.get("elapsed_ms", 0) for e in full_log)
    hops = len(online_log)
    snr_val = snr(online_log, result)
    ec = evidence_complete(result)
    return {
        "chars": total_chars,
        "ms": total_ms,
        "hops": hops,
        "snr": snr_val,
        "ec": ec,
    }


def aggregate(metrics_list: list[dict]) -> dict:
    if not metrics_list:
        return {}
    n = len(metrics_list)
    return {
        "chars": sum(m["chars"] for m in metrics_list) / n,
        "ms": sum(m["ms"] for m in metrics_list) / n,
        "hops": sum(m["hops"] for m in metrics_list) / n,
        "snr": sum(m["snr"] for m in metrics_list) / n,
        "ec_pct": sum(1 for m in metrics_list if m["ec"]) / n * 100,
        "n": n,
    }


def main():
    verbose = "--verbose" in sys.argv
    out_path = None
    if "--output" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--output") + 1])

    iacpg_metrics = []
    cpg_metrics = []

    for dt in DEFECT_TYPES:
        for case_id in CASES:
            for arch in ARCHS:
                analysis_dir = MIBENCH / dt / case_id / arch / "improved_interrupt_analysis"
                if not analysis_dir.exists():
                    continue

                m_iacpg = collect_metrics(
                    analysis_dir,
                    dt,
                    case_id,
                    arch,
                    "detection_result.json",
                    "tool_call_log.jsonl",
                )
                if m_iacpg:
                    iacpg_metrics.append(m_iacpg)
                    if verbose:
                        print(f"  IACPG {dt}/{case_id}/{arch}: {m_iacpg}")

                m_cpg = collect_metrics(
                    analysis_dir,
                    dt,
                    case_id,
                    arch,
                    "detection_result_cpg.json",
                    "tool_call_log_cpg.jsonl",
                    "detection_result_cpg_backup.json",
                    "tool_call_log_cpg_backup.jsonl",
                )
                if m_cpg:
                    cpg_metrics.append(m_cpg)
                    if verbose:
                        print(f"  CPG   {dt}/{case_id}/{arch}: {m_cpg}")

    iacpg_agg = aggregate(iacpg_metrics)
    cpg_agg = aggregate(cpg_metrics)

    print("\n=== RQ2: Table 3 ===")
    print(f"{'指标':<20} {'CPG':>12} {'IACPG':>12}")
    print("-" * 46)

    def row(label, key, fmt=".1f"):
        cv = cpg_agg.get(key, float("nan"))
        iv = iacpg_agg.get(key, float("nan"))
        print(f"{label:<20} {cv:>12{fmt}} {iv:>12{fmt}}")

    row("返回数据量 (Chars)", "chars", ".0f")
    row("响应时间 (ms)", "ms", ".1f")
    row("推理跳数 (Hops)", "hops", ".1f")
    row("信噪比 (SNR%)", "snr", ".2f")
    row("证据完整度 (EC%)", "ec_pct", ".1f")
    print(f"\n样本数: CPG={cpg_agg.get('n', 0)}, IACPG={iacpg_agg.get('n', 0)}")

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"table3": {"CPG": cpg_agg, "IACPG": iacpg_agg}}, indent=2, ensure_ascii=False))
        print(f"\n结果已写入 {out_path}")


if __name__ == "__main__":
    main()
