#!/usr/bin/env python3
"""RQ1 LLM基线: 直接调用 LLM API 进行中断语义提取，与静态分析（Stage 1）对比（Table 2 扩展）。

让 LLM 阅读源码后直接回答四个维度：
  - ISR识别：哪些函数是中断处理函数？
  - IRQ Mask：有哪些中断开关操作（enable/disable）？
  - Priority：各 ISR 的优先级是多少？
  - Shared Access：哪些变量在主函数和 ISR 之间共享？

结果存到：<case>/improved_interrupt_analysis/rq1_llm_result.json
评估结果与 eval_rq1.py 使用同一套 P/R/F1 逻辑，输出可直接与静态分析列对比。

用法：
  python scripts/eval_rq1_llm.py [--dry-run] [--only AtomicityViolation] [--verbose] [--output results/rq1_llm.json]
  ANTHROPIC_API_KEY=xxx python scripts/eval_rq1_llm.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import yaml

from meta_utils import load_meta_checked

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

# ── Prompt ────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT_TEMPLATE = """\
以下是一段嵌入式 C 代码（目标架构：{arch}）：

```c
{source}
```

请仔细分析上述代码，提取以下四类中断相关语义信息，并严格按照指定 JSON 格式输出，不要输出任何其他内容。

【提取目标】
1. ISR函数（interrupt_functions）：所有中断服务程序/中断处理函数的名称。
   判断依据：函数命名约定（如 xxx_IRQHandler、ISR(xxx_vect)、__interrupt void xxx 等）、
   中断向量注册、或被中断控制器使能的函数。

2. 中断开关操作（switches）：代码中所有使能/禁止中断的操作。
   包括：全局中断开关（sei/cli、__enable_irq/__disable_irq 等）
   以及单个中断的开关（NVIC_EnableIRQ、PLIC_EnableIRQ、NVIC_DisableIRQ 等）。

3. ISR优先级（priorities）：各 ISR 的中断优先级数值。
   来源：NVIC_SetPriority、PLIC_SetPriority、HAL_NVIC_SetPriority 等显式设置调用。
   若代码中没有显式设置则不填（返回空列表）。

4. 共享变量（shared_variables）：在主函数（main/task函数）和 ISR 之间都被访问的全局变量。
   关注：在 ISR 中被读写、且在主函数逻辑中也被读写的变量。

【输出格式（严格遵守，不要输出其他内容）】
{{
  "interrupt_functions": [
    {{"name": "<函数名>", "reason": "<简要判断依据>"}}
  ],
  "switches": [
    {{"op": "enable"|"disable", "target": "<IRQn名称或global>", "api": "<调用的API名>"}}
  ],
  "priorities": [
    {{"name": "<ISR函数名>", "priority": <整数优先级值>}}
  ],
  "shared_variables": [
    {{"name": "<变量名>", "reason": "<简要说明为何判断为共享>"}}
  ]
}}
"""

# ── LLM 调用 ──────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    import anthropic
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**kwargs)
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    # 跳过 ThinkingBlock，取第一个 TextBlock
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}


def read_source(case_dir: Path) -> str:
    c_files = list(case_dir.glob("*.c")) + list(case_dir.glob("*.cpp"))
    if not c_files:
        return ""
    return c_files[0].read_text(encoding="utf-8", errors="replace")


def run_case(case_dir: Path, dry_run: bool = False) -> dict:
    source = read_source(case_dir)
    if not source:
        return {"error": "no source file found"}

    arch = case_dir.name          # e.g. "arm", "avr"
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(arch=arch, source=source)

    if dry_run:
        return {"dry_run": True, "prompt_chars": len(prompt)}

    raw = call_llm(prompt)
    result = parse_json_response(raw)
    result["_raw_response"] = raw   # 保留原始响应便于调试
    return result


# ── 评估逻辑（与 eval_rq1.py 完全一致） ────────────────────────────────────────

def load_meta(defect_type: str, case_id: str, arch: str) -> dict | None:
    p = MIBENCH / defect_type / "meta" / f"{case_id}_{arch}.yml"
    return load_meta_checked(p, case_id, arch)


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def _normalize_target(t: str) -> str:
    return "" if t in ("", "global") else t


def eval_isr_llm(llm_result: dict, meta: dict) -> tuple[int, int, int]:
    """ISR识别：llm interrupt_functions vs meta handlers."""
    gt_names = {h["name"] for h in meta.get("interrupts", {}).get("handlers", [])}
    if not llm_result or "parse_error" in llm_result or not gt_names:
        return 0, 0, len(gt_names)
    pred_names = {f["name"] for f in llm_result.get("interrupt_functions", [])}
    tp = len(pred_names & gt_names)
    fp = len(pred_names - gt_names)
    fn = len(gt_names - pred_names)
    return tp, fp, fn


def eval_irq_mask_llm(llm_result: dict, meta: dict) -> tuple[int, int, int]:
    """IRQ Mask：llm switches vs meta switches."""
    gt = meta.get("interrupts", {}).get("switches", [])
    gt_set = {(s["op"], _normalize_target(s.get("target", ""))) for s in gt}
    if not llm_result or "parse_error" in llm_result:
        return 0, 0, len(gt_set)
    pred_set = set()
    for s in llm_result.get("switches", []):
        op = s.get("op", "")
        target = _normalize_target(s.get("target", ""))
        pred_set.add((op, target))
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    return tp, fp, fn


def eval_priority_llm(llm_result: dict, meta: dict) -> tuple[int, int, int]:
    """Priority：llm priorities vs meta handlers[].priority."""
    gt_handlers = meta.get("interrupts", {}).get("handlers", [])
    gt_set = {(h["name"], h.get("priority", 0)) for h in gt_handlers if "priority" in h}
    if not llm_result or "parse_error" in llm_result or not gt_set:
        return 0, 0, len(gt_set)
    pred_set = {(p["name"], p["priority"]) for p in llm_result.get("priorities", [])}
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    return tp, fp, fn


def eval_shared_access_llm(llm_result: dict, meta: dict) -> tuple[int, int, int]:
    """Shared Access：llm shared_variables vs meta defects[].variable."""
    gt_vars = {d["variable"] for d in meta.get("defects", [])}
    if not llm_result or "parse_error" in llm_result or not gt_vars:
        return 0, 0, len(gt_vars)
    pred_vars = {v["name"] for v in llm_result.get("shared_variables", []) if "name" in v}
    tp = len(pred_vars & gt_vars)
    fp = 0   # 与 eval_rq1.py 保持一致：多提取的共享变量不算误报
    fn = len(gt_vars - pred_vars)
    return tp, fp, fn


# ── 主流程 ─────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    out_path = None
    if "--output" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--output") + 1])

    if not dry_run and not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        print("ERROR: ANTHROPIC_AUTH_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    dims = ["ISR识别", "IRQ Mask", "Priority", "Shared Access"]
    totals = {d: [0, 0, 0] for d in dims}
    ok, fail, skip = 0, 0, 0

    defect_types = [only] if only else DEFECT_TYPES
    for dt in defect_types:
        for case_id in CASES:
            for arch in ARCHS:
                case_dir = MIBENCH / dt / case_id / arch
                if not case_dir.exists():
                    continue

                meta = load_meta(dt, case_id, arch)
                if meta is None:
                    continue

                out_dir = case_dir / "improved_interrupt_analysis"
                out_file = out_dir / "rq1_llm_result.json"

                tag = f"{dt}/{case_id}/{arch}"

                # 已有缓存则直接读取评估，不重复调用 LLM
                if out_file.exists():
                    llm_result = json.loads(out_file.read_text(encoding="utf-8"))
                    skip += 1
                else:
                    if dry_run:
                        result = run_case(case_dir, dry_run=True)
                        print(f"  DRY {tag}: {result['prompt_chars']} chars")
                        ok += 1
                        continue
                    try:
                        llm_result = run_case(case_dir)
                        out_dir.mkdir(exist_ok=True)
                        out_file.write_text(
                            json.dumps(llm_result, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        ok += 1
                        print(f"  OK  {tag}")
                        time.sleep(0.5)   # rate limit
                    except Exception as e:
                        fail += 1
                        print(f"  ERR {tag}: {e}", file=sys.stderr)
                        continue

                # 评估
                results = {
                    "ISR识别":      eval_isr_llm(llm_result, meta),
                    "IRQ Mask":     eval_irq_mask_llm(llm_result, meta),
                    "Priority":     eval_priority_llm(llm_result, meta),
                    "Shared Access": eval_shared_access_llm(llm_result, meta),
                }
                for dim, (tp, fp, fn) in results.items():
                    totals[dim][0] += tp
                    totals[dim][1] += fp
                    totals[dim][2] += fn
                if verbose:
                    print(f"  {tag}: {results}")

    print(f"\nDone: {ok} ok, {skip} cached, {fail} failed")

    # 打印汇总表
    print("\n=== RQ1 LLM基线: 中断语义提取精度（对比 Table 2）===")
    print(f"{'维度':<16} {'TP':>5} {'FP':>5} {'FN':>5} {'P':>7} {'R':>7} {'F1':>7}")
    print("-" * 60)
    table = {}
    for dim in dims:
        tp, fp, fn = totals[dim]
        p, r, f1 = prf(tp, fp, fn)
        print(f"{dim:<16} {tp:>5} {fp:>5} {fn:>5} {p:>7.3f} {r:>7.3f} {f1:>7.3f}")
        table[dim] = {"tp": tp, "fp": fp, "fn": fn,
                      "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"table2_llm": table}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n结果已写入 {out_path}")


if __name__ == "__main__":
    main()
