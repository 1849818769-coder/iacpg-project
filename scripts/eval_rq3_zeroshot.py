#!/usr/bin/env python3
"""RQ3 Zero-shot: 对 64 个用例调用 LLM API 进行零样本缺陷检测。

输出：<case>/improved_interrupt_analysis/detection_result_zeroshot.json

用法：
  python scripts/eval_rq3_zeroshot.py [--dry-run] [--cases simple_001~004]
  ANTHROPIC_API_KEY=xxx python scripts/eval_rq3_zeroshot.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIBENCH = PROJECT_ROOT / "testfiles" / "MiBench"
DEFECT_TYPES = ["AtomicityViolation", "BufferOverflow", "DivideByZero", "MultiwordDataRace"]
ARCHS = ["arm", "avr", "msp430", "riscv"]
CASES = [f"simple_{i:03d}" for i in range(1, 7)]

DEFECT_DEFINITIONS = """
请判断以下代码是否存在这四类中断并发缺陷：
1. atomicity_violation — 共享状态在主流程的依赖访问序列中被中断改写
2. interrupt_aware_array_oob — 共享索引/边界状态在验证后、数组访问前被中断改写
3. interrupt_aware_div_zero — 共享分母状态在非零验证后、除法前被中断改写
4. multiword_data_race — 宽于平台原子字宽的共享对象在主流程与中断间发生非原子访问
"""

OUTPUT_SCHEMA = """
请以如下 JSON 格式输出检测结果（严格遵守字段名，不要输出其他内容）：
{
  "verdict": "single-label" | "multi-label" | "no_bug",
  "hit_types": ["<defect_type>", ...],
  "results": {
    "atomicity_violation": {
      "conclusion": "yes" | "no",
      "reason": "<brief_reason>"
    },
    "interrupt_aware_array_oob": {
      "conclusion": "yes" | "no",
      "reason": "<brief_reason>"
    },
    "interrupt_aware_div_zero": {
      "conclusion": "yes" | "no",
      "reason": "<brief_reason>"
    },
    "multiword_data_race": {
      "conclusion": "yes" | "no",
      "reason": "<brief_reason>"
    }
  }
}
"""


def read_source(case_dir: Path) -> str:
    c_files = list(case_dir.glob("*.c")) + list(case_dir.glob("*.cpp"))
    if not c_files:
        return ""
    return c_files[0].read_text(encoding="utf-8", errors="replace")


def strip_comments(source: str) -> str:
    """去除 C/C++ 注释，保留换行结构和预处理指令。"""
    # 匹配: 块注释 | 行注释 | 字符串字面量 | 字符字面量
    pattern = r'(/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    def _replace(m):
        s = m.group(0)
        if s.startswith(("//")):
            return ""  # 行注释 → 删除（保留该行其余部分）
        if s.startswith("/*"):
            # 块注释 → 保留等量换行以维持行号结构
            return "\n" * s.count("\n")
        return s  # 字符串/字符字面量 → 原样保留
    return re.sub(pattern, _replace, source)


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
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    # 跳过 ThinkingBlock，取第一个 TextBlock
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def parse_json_response(text: str) -> dict:
    text = text.strip()
    # 提取 JSON 块
    if "```" in text:
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}


def run_case(case_dir: Path, dry_run: bool = False) -> dict:
    source = read_source(case_dir)
    if not source:
        return {"error": "no source file found"}

    source = strip_comments(source)

    prompt = (
        f"以下是一段嵌入式 C 代码：\n\n"
        f"```c\n{source}\n```\n\n"
        f"{DEFECT_DEFINITIONS}\n"
        f"按如下 JSON 格式输出（不要输出其他内容）：\n"
        f"{OUTPUT_SCHEMA}"
    )

    if dry_run:
        return {"dry_run": True, "prompt_chars": len(prompt)}

    result = call_llm(prompt)
    return parse_json_response(result)


def main():
    dry_run = "--dry-run" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    if not dry_run and not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        print("ERROR: ANTHROPIC_AUTH_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    defect_types = [only] if only else DEFECT_TYPES
    ok, fail, skip = 0, 0, 0
    for dt in defect_types:
        for case_id in CASES:
            for arch in ARCHS:
                case_dir = MIBENCH / dt / case_id / arch
                if not case_dir.exists():
                    continue

                out_dir = case_dir / "improved_interrupt_analysis"
                out_file = out_dir / "detection_result_zeroshot.json"
                if out_file.exists():
                    skip += 1
                    continue

                tag = f"{dt}/{case_id}/{arch}"
                try:
                    result = run_case(case_dir, dry_run=dry_run)
                    if not dry_run:
                        out_dir.mkdir(exist_ok=True)
                        out_file.write_text(
                            json.dumps(result, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                    ok += 1
                    print(f"  OK  {tag}")
                    if not dry_run:
                        time.sleep(0.5)  # rate limit
                except Exception as e:
                    fail += 1
                    print(f"  ERR {tag}: {e}", file=sys.stderr)

    print(f"\nDone: {ok} ok, {skip} skipped, {fail} failed")


if __name__ == "__main__":
    main()
