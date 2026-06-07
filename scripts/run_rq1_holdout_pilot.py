#!/usr/bin/env python3
"""Run the RQ1 rule-holdout pilot on a single architecture."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import yaml

from rq1_eval_utils import CASES, DEFECT_TYPES, MIBENCH, evaluate_rq1, load_json
from ice_core.static_analysis.extractors.unified_parser import UnifiedInterruptParser


DEFAULT_ARCH = "msp430"
RULE_ARCH_MAP = {
    "arm": "ARM",
    "avr": "AVR",
    "msp430": "MSP430",
    "riscv": "RISC-V",
}
PROMPT_TEMPLATE = """\
You are repairing missing ISR annotations after a static rule-holdout experiment.

Target ISA: {arch}
Case: {case_tag}

Known static facts:
- already identified interrupt functions: {known_interrupts}
- identified main functions: {known_mains}
- static interrupt switches: {switches}
- static priority entries: {priorities}

Candidate regular functions (choose ISR candidates only from this list):
{regular_functions}

Source code:
```c
{source}
```

Task:
Select only the functions from the candidate list that are true interrupt service routines.
Do not repeat already identified interrupt functions or main functions.
For AVR specifically, names appearing inside ISR(<name>) macro declarations are valid ISR candidates even if they do not appear in the regular function list.
If no extra ISR should be added, return an empty list.

Return strict JSON only:
{{
  "interrupt_functions": [
    {{"name": "<function name>", "priority": <int>, "reason": "<short reason>"}}
  ]
}}
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Run RQ1 rule-holdout pilot.")
    parser.add_argument("--arch", default=DEFAULT_ARCH, help="Pilot architecture (default: msp430)")
    parser.add_argument("--experiment-root", type=Path, default=None, help="Optional explicit experiment root")
    parser.add_argument("--skip-group-c", action="store_true", help="Only run Group A/B")
    parser.add_argument("--retry-empty-only", action="store_true", help="Only rerun Group C cases whose previous raw response was empty")
    parser.add_argument("--retry-failed-only", action="store_true", help="Only rerun Group C cases whose previous completion failed at API or parsing stage")
    parser.add_argument("--case-tag", dest="case_tags", action="append", help="Explicit case tag(s) to rerun, e.g. DivideByZero/simple_001/riscv")
    parser.add_argument("--empty-retries", type=int, default=2, help="Retry count for empty LLM responses")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def default_experiment_root(arch: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / "rq1_holdout" / f"{arch}_pilot_{stamp}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def rule_yaml_path() -> Path:
    return project_root() / "ice_core" / "knowledge_base" / "interrupt_info.yml"


def stage1_runner_path() -> Path:
    return Path(__file__).resolve().with_name("run_stage1_case.py")


def build_masked_yaml(arch: str, out_path: Path):
    data = yaml.safe_load(rule_yaml_path().read_text(encoding="utf-8"))
    original = data.get("interrupt_function_patterns", [])
    rule_arch = RULE_ARCH_MAP.get(arch.lower(), arch.upper())
    data["interrupt_function_patterns"] = [
        item for item in original if item.get("arch") != rule_arch
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def case_entries(arch: str):
    entries = []
    for defect_type in DEFECT_TYPES:
        for case_id in CASES:
            case_dir = MIBENCH / defect_type / case_id / arch
            if case_dir.exists():
                entries.append((defect_type, case_id, arch, case_dir))
    return entries


def run_stage1_case(case_dir: Path, output_dir: Path, masked_yaml: Path, verbose: bool = False) -> dict:
    env = os.environ.copy()
    env["INTERRUPT_INFO_YAML_PATH"] = str(masked_yaml.resolve())
    cmd = [
        sys.executable,
        str(stage1_runner_path()),
        "--project-path",
        str(case_dir),
        "--output-dir",
        str(output_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    result = {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }
    if verbose:
        print(f"[Group B] {case_dir}: rc={proc.returncode}")
    return result


def read_source(case_dir: Path) -> str:
    c_files = list(case_dir.glob("*.c")) + list(case_dir.glob("*.cpp"))
    if not c_files:
        return ""
    return c_files[0].read_text(encoding="utf-8", errors="replace")


def _single_llm_call(prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        import anthropic

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
        text_blocks = []
        for block in msg.content:
            if hasattr(block, "text"):
                text = (block.text or "").strip()
                if text:
                    text_blocks.append(text)
        return "\n".join(text_blocks).strip()

    proc = subprocess.run(
        ["claude", "--print", "--dangerously-skip-permissions", prompt],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def call_llm(prompt: str, empty_retries: int = 2) -> dict:
    attempts = 0
    text = ""
    last_error = None
    total_attempts = empty_retries + 1
    for attempt_idx in range(total_attempts):
        attempts += 1
        try:
            text = _single_llm_call(prompt)
        except Exception as exc:
            last_error = exc
            msg = str(exc)
            if "529" in msg or "overloaded_error" in msg.lower():
                if attempt_idx < total_attempts - 1:
                    time.sleep(min(2 ** attempt_idx, 8))
                    continue
                raise
            raise
        if text.strip():
            return {"text": text, "attempts": attempts, "status": "ok"}
        if attempt_idx < total_attempts - 1:
            time.sleep(min(2 ** attempt_idx, 8))
    return {
        "text": text,
        "attempts": attempts,
        "status": "empty_response" if last_error is None else "empty_after_retry",
    }


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if not text:
        return {"empty_response": True, "raw_response": ""}
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw_response": text}


def summarize_switches(switches: list[dict]) -> list[dict]:
    summary = []
    for sw in switches[:8]:
        summary.append(
            {
                "line": sw.get("line_number"),
                "operation": sw.get("operation", sw.get("op")),
                "target": sw.get("target", sw.get("irq", "")),
                "function": sw.get("function", ""),
            }
        )
    return summary


def summarize_priorities(priorities: dict | list) -> list[dict]:
    entries = priorities.values() if isinstance(priorities, dict) else priorities
    summary = []
    for entry in list(entries)[:8]:
        summary.append(
            {
                "name": entry.get("function_name", entry.get("name", "")),
                "priority": entry.get("priority"),
            }
        )
    return summary


def format_regular_functions(functions_json: dict) -> str:
    lines = []
    for fn in functions_json.get("regular_functions", []):
        name = fn.get("name", "")
        line = fn.get("line_number", 0)
        definition = fn.get("function_definition", "").strip()
        lines.append(f"- {name} (line {line}): {definition}")
    return "\n".join(lines) if lines else "- <none>"


def extract_source_interrupt_candidates(case_dir: Path, arch: str) -> dict[str, dict]:
    text = read_source(case_dir)
    candidates: dict[str, dict] = {}
    if arch == "avr":
        for match in re.finditer(r"ISR\s*\(\s*(\w+_vect)\s*\)", text):
            name = match.group(1)
            line = text[:match.start()].count("\n") + 1
            function_definition, function_body = UnifiedInterruptParser._extract_function_definition_and_body(
                text, match.start()
            )
            candidates[name] = {
                "name": name,
                "line_number": line,
                "function_definition": function_definition or f"ISR({name})",
                "function_body": function_body,
                "file_path": str(next(iter(case_dir.glob('*.c')), "")),
                "architecture": "AVR",
                "source": "avr_isr_macro",
            }
    return candidates


def format_extra_candidates(extra_candidates: dict[str, dict]) -> str:
    if not extra_candidates:
        return "- <none>"
    lines = []
    for name, item in extra_candidates.items():
        lines.append(
            f"- {name} (line {item.get('line_number', 0)}): {item.get('function_definition', '').strip()}"
        )
    return "\n".join(lines)


def build_completion_prompt(case_dir: Path, analysis_dir: Path, arch: str) -> tuple[str, dict, dict[str, dict]]:
    functions = load_json(analysis_dir / "functions.json") or {}
    switches = load_json(analysis_dir / "interrupt_switches.json") or []
    priorities = load_json(analysis_dir / "interrupt_priorities.json") or {}
    extra_candidates = extract_source_interrupt_candidates(case_dir, arch)
    payload = {
        "case_tag": f"{case_dir.parent.parent.name}/{case_dir.parent.name}/{arch}",
        "arch": arch,
        "known_interrupts": [f["name"] for f in functions.get("interrupt_functions", [])],
        "known_mains": [f["name"] for f in functions.get("main_functions", [])],
        "switches": summarize_switches(switches),
        "priorities": summarize_priorities(priorities),
        "regular_functions": format_regular_functions(functions),
        "extra_candidates": format_extra_candidates(extra_candidates),
        "source": read_source(case_dir),
    }
    prompt = PROMPT_TEMPLATE.replace(
        "Candidate regular functions (choose ISR candidates only from this list):\n{regular_functions}\n\nSource code:",
        "Candidate regular functions (choose ISR candidates only from this list unless additional source-derived candidates are listed below):\n{regular_functions}\n\nAdditional source-derived interrupt candidates:\n{extra_candidates}\n\nSource code:",
    )
    return prompt.format(**payload), payload, extra_candidates


def normalize_completion_patch(raw_patch: dict, analysis_dir: Path, extra_candidates: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
    functions = load_json(analysis_dir / "functions.json") or {}
    all_functions = {}
    for category in ("interrupt_functions", "main_functions", "regular_functions"):
        for fn in functions.get(category, []):
            all_functions[fn["name"]] = fn
    extra_candidates = extra_candidates or {}

    existing_interrupts = {fn["name"] for fn in functions.get("interrupt_functions", [])}
    mains = {fn["name"] for fn in functions.get("main_functions", [])}
    accepted = []
    stats = {
        "proposed_candidates": 0,
        "accepted_candidates": 0,
        "rejected_candidates": 0,
        "rejected_reasons": [],
    }

    for item in raw_patch.get("interrupt_functions", []):
        stats["proposed_candidates"] += 1
        name = str(item.get("name", "")).strip()
        if not name:
            stats["rejected_candidates"] += 1
            stats["rejected_reasons"].append("empty_name")
            continue
        if name not in all_functions and name not in extra_candidates:
            stats["rejected_candidates"] += 1
            stats["rejected_reasons"].append(f"missing_ast:{name}")
            continue
        if name in existing_interrupts:
            stats["rejected_candidates"] += 1
            stats["rejected_reasons"].append(f"already_interrupt:{name}")
            continue
        if name in mains:
            stats["rejected_candidates"] += 1
            stats["rejected_reasons"].append(f"is_main:{name}")
            continue
        priority = item.get("priority", 1)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = 1
        accepted_item = {"name": name, "priority": priority, "reason": item.get("reason", "")}
        if name in extra_candidates:
            accepted_item["candidate_source"] = extra_candidates[name].get("source", "extra_candidate")
        accepted.append(accepted_item)

    stats["accepted_candidates"] = len(accepted)
    return accepted, stats


def infer_interrupt_number(name: str) -> int | None:
    match = re.search(r"_(\d+)$", name)
    return int(match.group(1)) if match else None


def incremental_merge_interrupts(
    analysis_dir: Path,
    accepted: list[dict],
    extra_candidates: dict[str, dict] | None = None,
) -> dict:
    functions_path = analysis_dir / "functions.json"
    priorities_path = analysis_dir / "interrupt_priorities.json"

    functions = load_json(functions_path) or {"interrupt_functions": [], "main_functions": [], "regular_functions": []}
    old_priorities = load_json(priorities_path) or {}
    extra_candidates = extra_candidates or {}

    existing_interrupts = deepcopy(functions.get("interrupt_functions", []))
    mains = deepcopy(functions.get("main_functions", []))
    regulars = deepcopy(functions.get("regular_functions", []))
    regular_by_name = {fn["name"]: fn for fn in regulars}
    accepted_names = {item["name"] for item in accepted}

    moved_interrupts = []
    synthetic_interrupts = []
    kept_regulars = []
    for fn in regulars:
        if fn["name"] in accepted_names:
            new_fn = dict(fn)
            accepted_item = next(item for item in accepted if item["name"] == fn["name"])
            new_fn["type"] = "interrupt"
            new_fn["priority"] = accepted_item["priority"]
            new_fn["interrupt_number"] = infer_interrupt_number(new_fn["name"])
            moved_interrupts.append(new_fn)
        else:
            kept_regulars.append(fn)

    regular_names = {fn["name"] for fn in regulars}
    for item in accepted:
        if item["name"] in regular_names:
            continue
        if item["name"] not in extra_candidates:
            continue
        meta = extra_candidates[item["name"]]
        synthetic_interrupts.append(
            {
                "name": item["name"],
                "file_path": meta.get("file_path", ""),
                "line_number": meta.get("line_number", 0),
                "function_definition": meta.get("function_definition", ""),
                "function_body": meta.get("function_body", ""),
                "type": "interrupt",
                "priority": item["priority"],
                "interrupt_number": infer_interrupt_number(item["name"]),
                "architecture": meta.get("architecture", "Generic"),
            }
        )

    merged_interrupts = sorted(
        existing_interrupts + moved_interrupts + synthetic_interrupts,
        key=lambda item: (item.get("line_number", 0), item.get("name", "")),
    )

    with open(functions_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "interrupt_functions": merged_interrupts,
                "main_functions": mains,
                "regular_functions": kept_regulars,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    new_priorities = {}
    for fn in merged_interrupts:
        name = fn["name"]
        if name in old_priorities:
            entry = dict(old_priorities[name])
            entry["priority"] = fn.get("priority", entry.get("priority", 1))
        else:
            entry = {
                "function_name": name,
                "priority": fn.get("priority", 1),
                "type": "interrupt",
                "source": "completion",
                "interrupt_number": fn.get("interrupt_number"),
                "architecture": fn.get("architecture", "Generic"),
                "file_path": fn.get("file_path", ""),
                "line_number": fn.get("line_number", 0),
            }
        new_priorities[name] = entry

    with open(priorities_path, "w", encoding="utf-8") as f:
        json.dump(new_priorities, f, indent=2, ensure_ascii=False)

    return {
        "existing_interrupts": len(existing_interrupts),
        "accepted_interrupts": len(moved_interrupts) + len(synthetic_interrupts),
        "synthetic_interrupts": len(synthetic_interrupts),
        "final_interrupts": len(merged_interrupts),
        "final_regulars": len(kept_regulars),
        "candidate_regulars": len(regular_by_name),
    }


def rebuild_shared_variables(analysis_dir: Path) -> int:
    functions = load_json(analysis_dir / "functions.json") or {}
    call_graph = load_json(analysis_dir / "function_call_relations.json") or {}
    variable_operations = load_json(analysis_dir / "variable_operations.json") or []
    global_variables = load_json(analysis_dir / "global_variables.json") or []

    call_relations = call_graph.get("call_relations", []) if isinstance(call_graph, dict) else []
    global_map = {item["name"]: item for item in global_variables if "name" in item}
    roots = {
        fn["name"]
        for category in ("main_functions", "interrupt_functions")
        for fn in functions.get(category, [])
    }

    reachable = set(roots)
    changed = True
    while changed:
        changed = False
        for relation in call_relations:
            caller = relation.get("caller")
            callee = relation.get("called")
            if caller in reachable and callee and callee not in reachable:
                reachable.add(callee)
                changed = True

    shared_names = []
    for op in variable_operations:
        var_name = op.get("variable")
        if op.get("function") in reachable and var_name in global_map and var_name not in shared_names:
            shared_names.append(var_name)

    rebuilt = []
    for name in shared_names:
        base = dict(global_map[name])
        base.setdefault("data_structure", "unknown")
        base["access_count"] = sum(1 for op in variable_operations if op.get("variable") == name)
        rebuilt.append(base)

    out_path = analysis_dir / "shared_variables.json"
    out_path.write_text(json.dumps(rebuilt, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(rebuilt)


def evaluate_group(analysis_root: Path, arch: str) -> dict:
    return evaluate_rq1(analysis_root=analysis_root, archs=[arch])


def extract_f1_table(result: dict) -> dict:
    return {dim: row["f1"] for dim, row in result["table2"].items()}


def compute_recovery(group_a: dict, group_b: dict, group_c: dict) -> dict:
    recovery = {}
    for dim in group_a["table2"]:
        a_f1 = group_a["table2"][dim]["f1"]
        b_f1 = group_b["table2"][dim]["f1"]
        c_f1 = group_c["table2"][dim]["f1"]
        denom = a_f1 - b_f1
        recovery[dim] = None if abs(denom) < 1e-9 else round((c_f1 - b_f1) / denom, 4)
    return recovery


def case_tag(defect_type: str, case_id: str, arch: str) -> str:
    return f"{defect_type}/{case_id}/{arch}"


def case_completion_path(group_c_root: Path, defect_type: str, case_id: str, arch: str) -> Path:
    return group_c_root / defect_type / case_id / arch / "improved_interrupt_analysis" / "rq1_holdout_completion.json"


def collect_completion_stats(group_c_root: Path, cases: list[tuple[str, str, str, Path]]) -> dict:
    stats = {
        "completion_triggered_cases": 0,
        "empty_responses": 0,
        "json_parse_failures": 0,
        "proposed_candidates": 0,
        "accepted_candidates": 0,
        "rejected_candidates": 0,
        "cases": {},
    }
    for defect_type, case_id, arch, _case_dir in cases:
        path = case_completion_path(group_c_root, defect_type, case_id, arch)
        if not path.exists():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        raw = item.get("raw_response", "")
        parsed = item.get("parsed_response", {})
        validation = item.get("validation", {})
        tag = case_tag(defect_type, case_id, arch)

        stats["completion_triggered_cases"] += 1
        if parsed.get("empty_response") or raw == "":
            stats["empty_responses"] += 1
        elif parsed.get("parse_error"):
            stats["json_parse_failures"] += 1

        stats["proposed_candidates"] += validation.get("proposed_candidates", 0)
        stats["accepted_candidates"] += validation.get("accepted_candidates", 0)
        stats["rejected_candidates"] += validation.get("rejected_candidates", 0)
        stats["cases"][tag] = {
            "accepted_interrupts": item.get("accepted_interrupts", []),
            "validation": validation,
            "merge_stats": item.get("merge_stats", {}),
            "shared_variables_rebuilt": item.get("shared_variables_rebuilt"),
            "response_status": item.get("response_status"),
            "llm_attempts": item.get("llm_attempts"),
        }
    return stats


def find_empty_response_tags(group_c_root: Path, cases: list[tuple[str, str, str, Path]]) -> set[str]:
    tags = set()
    for defect_type, case_id, arch, _case_dir in cases:
        path = case_completion_path(group_c_root, defect_type, case_id, arch)
        if not path.exists():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        raw = item.get("raw_response", "")
        parsed = item.get("parsed_response", {})
        if parsed.get("empty_response") or raw == "":
            tags.add(case_tag(defect_type, case_id, arch))
    return tags


def find_failed_case_tags(group_c_root: Path, cases: list[tuple[str, str, str, Path]]) -> set[str]:
    tags = set()
    for defect_type, case_id, arch, _case_dir in cases:
        path = case_completion_path(group_c_root, defect_type, case_id, arch)
        if not path.exists():
            tags.add(case_tag(defect_type, case_id, arch))
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        raw = item.get("raw_response", "")
        parsed = item.get("parsed_response", {})
        status = item.get("response_status", "ok")
        if (
            status != "ok"
            or parsed.get("empty_response")
            or parsed.get("parse_error")
            or raw == ""
        ):
            tags.add(case_tag(defect_type, case_id, arch))
    return tags


def main():
    args = parse_args()
    arch = args.arch
    exp_root = (args.experiment_root or default_experiment_root(arch)).resolve()
    group_b_root = exp_root / "group_b"
    group_c_root = exp_root / "group_c"
    masked_yaml = exp_root / f"interrupt_info_holdout_{arch}.yml"
    exp_root.mkdir(parents=True, exist_ok=True)

    cases = case_entries(arch)
    if not cases:
        raise SystemExit(f"No cases found for arch={arch}")

    build_masked_yaml(arch, masked_yaml)

    baseline = evaluate_rq1(archs=[arch])
    (exp_root / "group_a_eval.json").write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")

    rerun_only_mode = bool(args.retry_empty_only or args.retry_failed_only or args.case_tags)
    if not rerun_only_mode:
        stage1_logs = {}
        for defect_type, case_id, case_arch, case_dir in cases:
            output_dir = group_b_root / defect_type / case_id / case_arch / "improved_interrupt_analysis"
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            stage1_logs[case_tag(defect_type, case_id, case_arch)] = run_stage1_case(
                case_dir, output_dir, masked_yaml, verbose=args.verbose
            )

        group_b = evaluate_group(group_b_root, arch)
        (exp_root / "group_b_eval.json").write_text(json.dumps(group_b, indent=2, ensure_ascii=False), encoding="utf-8")
        (exp_root / "group_b_stage1_logs.json").write_text(json.dumps(stage1_logs, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        group_b_path = exp_root / "group_b_eval.json"
        if not group_b_path.exists():
            raise SystemExit("--retry-empty-only requires existing group_b_eval.json")
        group_b = json.loads(group_b_path.read_text(encoding="utf-8"))

    summary = {
        "arch": arch,
        "experiment_root": str(exp_root),
        "masked_yaml": str(masked_yaml),
        "group_a": baseline,
        "group_b": group_b,
    }

    if not args.skip_group_c:
        target_tags = None
        if args.case_tags:
            target_tags = set(args.case_tags)
            if args.verbose:
                print(f"[Group C] case_tag targets={sorted(target_tags)}")
        elif args.retry_failed_only:
            target_tags = find_failed_case_tags(group_c_root, cases)
            if args.verbose:
                print(f"[Group C] retry_failed_only targets={sorted(target_tags)}")
        elif args.retry_empty_only:
            target_tags = find_empty_response_tags(group_c_root, cases)
            if args.verbose:
                print(f"[Group C] retry_empty_only targets={sorted(target_tags)}")

        for defect_type, case_id, case_arch, case_dir in cases:
            current_tag = case_tag(defect_type, case_id, case_arch)
            if target_tags is not None and current_tag not in target_tags:
                continue

            src_analysis = group_b_root / defect_type / case_id / case_arch / "improved_interrupt_analysis"
            dst_analysis = group_c_root / defect_type / case_id / case_arch / "improved_interrupt_analysis"
            dst_analysis.parent.mkdir(parents=True, exist_ok=True)
            if dst_analysis.exists():
                shutil.rmtree(dst_analysis)
            shutil.copytree(src_analysis, dst_analysis)

            prompt, prompt_payload, extra_candidates = build_completion_prompt(case_dir, dst_analysis, arch)
            llm_result = call_llm(prompt, empty_retries=args.empty_retries)
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
                accepted, validation = normalize_completion_patch(parsed, dst_analysis, extra_candidates)

            merge_stats = incremental_merge_interrupts(dst_analysis, accepted, extra_candidates)
            rebuilt_shared = rebuild_shared_variables(dst_analysis)

            case_result = {
                "prompt_payload": prompt_payload,
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
            (dst_analysis / "rq1_holdout_completion.json").write_text(
                json.dumps(case_result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        group_c = evaluate_group(group_c_root, arch)
        recovery = compute_recovery(baseline, group_b, group_c)
        completion_stats = collect_completion_stats(group_c_root, cases)
        (exp_root / "group_c_eval.json").write_text(json.dumps(group_c, indent=2, ensure_ascii=False), encoding="utf-8")
        (exp_root / "group_c_completion_stats.json").write_text(
            json.dumps(completion_stats, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summary["group_c"] = group_c
        summary["recovery_rate"] = recovery
        summary["completion_stats"] = completion_stats

    summary_path = exp_root / "pilot_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(
        {
            "status": "ok",
            "experiment_root": str(exp_root),
            "group_a_f1": extract_f1_table(baseline),
            "group_b_f1": extract_f1_table(group_b),
            "group_c_f1": extract_f1_table(summary["group_c"]) if "group_c" in summary else None,
            "recovery_rate": summary.get("recovery_rate"),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
