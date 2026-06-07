#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ICE MCP Server
面向 IACPG 构建与 Joern / IACPG 查询的 MCP 工具服务。
"""

import json
import os
import sys
import subprocess
import time
import functools
import runpy
from contextlib import contextmanager
from pathlib import Path


def _run_in_thread(fn, *args, **kwargs):
    """在独立线程中运行 fn（含独立事件循环），避免与 FastMCP 异步事件循环冲突。"""
    import asyncio as _asyncio
    from concurrent.futures import ThreadPoolExecutor as _TPE

    def _wrapper():
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        try:
            return fn(*args, **kwargs)
        finally:
            loop.close()

    with _TPE(max_workers=1) as ex:
        future = ex.submit(_wrapper)
        return future.result(timeout=600)

from mcp.server.fastmcp import FastMCP


def _resource_root() -> Path:
    """返回运行时资源根目录。

    普通源码运行时，资源根目录就是仓库根目录；PyInstaller 打包运行时，
    `sys._MEIPASS` 指向解包后的 `_internal` 资源目录，里面包含 scripts/
    和 ice_core/。
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent


_SERVER_DIR = str(_resource_root())
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

mcp = FastMCP("ice-interrupt-analyzer")

CONDA = os.environ.get("IACPG_CONDA_BIN", "conda")
CONDA_ENV = os.environ.get("IACPG_CONDA_ENV", "dd")
ROOT = Path(_SERVER_DIR)
QUERY_SCRIPT = ROOT / "scripts" / "query_iacpg.py"
FACTS_SCRIPT = ROOT / "scripts" / "build_interrupt_facts.py"
BUILD_IACPG_SCRIPT = ROOT / "scripts" / "build_iacpg.py"


_JOERN_TOOL_NAMES = frozenset(
    {"joern_import", "joern_workspace", "joern_query",
     "joern_methods", "joern_calls", "joern_identifiers"}
)


def _log_tool_call(func):
    """装饰器：记录每次 MCP 工具调用的名称、耗时和返回大小到 tool_call_log{suffix}.jsonl。

    后缀规则（优先级从高到低）：
    1. 环境变量 ICE_LOG_SUFFIX 若已设置，直接使用（兼容 run_case_claude.sh）。
    2. 若未设置，joern_* 工具自动使用 '_cpg'，其余工具使用 ''。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        project_path = kwargs.get("project_path") or (args[0] if args else None)
        if project_path and os.path.isdir(str(project_path)):
            log_dir = os.path.join(str(project_path), "improved_interrupt_analysis")
            os.makedirs(log_dir, exist_ok=True)
            env_suffix = os.environ.get("ICE_LOG_SUFFIX")
            if env_suffix is not None:
                suffix = env_suffix
            elif func.__name__ in _JOERN_TOOL_NAMES:
                suffix = "_cpg"
            else:
                suffix = ""
            log_path = os.path.join(log_dir, f"tool_call_log{suffix}.jsonl")
            entry = {
                "tool": func.__name__,
                "elapsed_ms": elapsed_ms,
                "result_chars": len(json.dumps(result, ensure_ascii=False)),
                "timestamp": time.time(),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return result
    return wrapper


@contextmanager
def _stdout_guarded():
    """将 stdout 重定向到 stderr，避免污染 MCP stdio 协议帧。"""
    import sys as _sys
    _old = _sys.stdout
    _sys.stdout = _sys.stderr
    try:
        yield
    finally:
        _sys.stdout = _old


@contextmanager
def _chdir(path: str):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _run_json_python(script_path: Path, *args: str) -> dict:
    current_env = os.environ.get("CONDA_DEFAULT_ENV")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "__run_script__", str(script_path), *args]
    elif os.environ.get("IACPG_PYTHON"):
        cmd = [os.environ["IACPG_PYTHON"], str(script_path), *args]
    elif current_env == CONDA_ENV:
        cmd = [sys.executable, str(script_path), *args]
    else:
        cmd = [CONDA, "run", "--no-capture-output", "-n", CONDA_ENV, "python", str(script_path), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "command": cmd,
    }


def _resolve_project_path(project_path: str) -> Path:
    p = Path(project_path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"project_path 不存在: {project_path}")
    return p


def _analysis_path(project: Path) -> Path:
    return project / "improved_interrupt_analysis"


def _facts_dir(project: Path) -> Path:
    return _analysis_path(project) / "interrupt_facts"


def _graph_path(project: Path) -> Path:
    return _analysis_path(project) / "iacpg_artifacts" / "iacpg.graphml"


def _ensure_graph(project: Path) -> Path:
    graph = _graph_path(project)
    if not graph.exists():
        raise FileNotFoundError(f"iacpg.graphml 不存在: {graph}")
    return graph


def _parse_joern_workspace_entries(workspace_result: dict | str) -> list[dict]:
    """Parse Joern workspace table output into structured entries."""
    if isinstance(workspace_result, dict):
        stdout = workspace_result.get("stdout", "")
    else:
        stdout = str(workspace_result)

    entries: list[dict] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("│"):
            continue
        parts = [part.strip() for part in line.split("│")[1:-1]]
        if len(parts) != 4:
            continue
        name, overlays, input_path, open_flag = parts
        if name in {"name", ""}:
            continue
        entries.append(
            {
                "name": name,
                "overlays": overlays,
                "input_path": input_path,
                "open": open_flag,
            }
        )
    return entries


def _case_arch_name(project: Path) -> str:
    """Best-effort canonical workspace name for case directories."""
    if project.parent.name and project.name:
        return f"{project.parent.name}_{project.name}"
    return project.name


def _workspace_entry_score(entry_name: str, project: Path) -> tuple[int, int, int]:
    """Prefer canonical case_arch names, then specific non-generic aliases."""
    canonical = _case_arch_name(project)
    score_exact = int(entry_name == canonical)
    score_contains = int(project.parent.name in entry_name and project.name in entry_name)
    score_nongeneric = int(entry_name not in {"arm", "avr", "msp430", "riscv"})
    return (score_exact, score_contains, score_nongeneric)


def _reuse_existing_joern_project(client, project: Path) -> str | None:
    """Open an existing Joern workspace project for the same input path."""
    workspace_result = client.workspace_query()
    entries = _parse_joern_workspace_entries(workspace_result)
    same_path = [e for e in entries if e.get("input_path") == str(project)]
    if not same_path:
        return None

    same_path.sort(
        key=lambda e: _workspace_entry_score(e["name"], project),
        reverse=True,
    )
    chosen = same_path[0]["name"]
    client.query(f'open("{chosen}")')
    client.current_project = chosen
    client.current_project_path = str(project)
    return chosen


def _run_analyzer_postprocess(analysis_path: str) -> dict:
    """汇总 Stage 1 产物，返回可直接给 MCP 客户端消费的统计信息。"""
    analysis_dir = Path(analysis_path)

    def _load_json(name: str, default):
        path = analysis_dir / name
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    functions = _load_json(
        "functions.json",
        {"interrupt_functions": [], "main_functions": [], "regular_functions": []},
    )
    switches_raw = _load_json("interrupt_switches.json", [])
    priorities = _load_json("interrupt_priorities.json", {})
    shared_variables = _load_json("shared_variables.json", [])
    global_variables = _load_json("global_variables.json", [])
    function_call_relations = _load_json("function_call_relations.json", {})

    switches = switches_raw if isinstance(switches_raw, list) else switches_raw.get("switches", [])
    call_relations = function_call_relations.get("call_relations", []) if isinstance(function_call_relations, dict) else []

    return {
        "functions": {
            "interrupt": len(functions.get("interrupt_functions", [])),
            "main": len(functions.get("main_functions", [])),
            "regular": len(functions.get("regular_functions", [])),
        },
        "interrupt_priorities": len(priorities),
        "interrupt_switches": len(switches),
        "mapped_switches": sum(1 for sw in switches if sw.get("mapped_targets")),
        "shared_variables": len(shared_variables) if isinstance(shared_variables, list) else 0,
        "global_variables": len(global_variables) if isinstance(global_variables, list) else 0,
        "function_calls": len(call_relations),
    }


# ---------------------------------------------------------------------------
# Stage 1: 中断语义提取
# ---------------------------------------------------------------------------


def _build_supplement_context(project_path: str, analysis_path: str) -> dict:
    import glob

    context: dict = {
        "source_files": [],
        "all_functions": [],
        "switch_operations": [],
    }

    for ext in ("*.c", "*.cpp", "*.h"):
        context["source_files"].extend(glob.glob(os.path.join(project_path, ext)))

    functions_file = os.path.join(analysis_path, "functions.json")
    if os.path.isfile(functions_file):
        try:
            with open(functions_file, "r", encoding="utf-8") as f:
                funcs = json.load(f)
            for category in ("interrupt_functions", "main_functions", "regular_functions"):
                for fn in funcs.get(category, []):
                    context["all_functions"].append({
                        "name": fn.get("name"),
                        "current_type": fn.get("type", category.replace("_functions", "")),
                        "line_number": fn.get("line_number"),
                        "file_path": fn.get("file_path"),
                    })
        except Exception:
            pass

    switches_file = os.path.join(analysis_path, "interrupt_switches.json")
    if os.path.isfile(switches_file):
        try:
            with open(switches_file, "r", encoding="utf-8") as f:
                switches = json.load(f)
            sw_list = switches if isinstance(switches, list) else switches.get("switches", [])
            for sw in sw_list:
                context["switch_operations"].append({
                    "line": sw.get("line_number"),
                    "operation": sw.get("operation"),
                    "target_param": sw.get("target"),
                    "code": sw.get("code"),
                    "in_function": sw.get("function"),
                    "current_mapped_targets": sw.get("mapped_targets", []),
                })
        except Exception:
            pass

    return context


def _merge_agent_patch(analysis_path: str, agent_patch: dict) -> dict:
    functions_file = os.path.join(analysis_path, "functions.json")
    switches_file = os.path.join(analysis_path, "interrupt_switches.json")
    priorities_file = os.path.join(analysis_path, "interrupt_priorities.json")

    warnings = []

    existing_funcs = {"interrupt_functions": [], "main_functions": [], "regular_functions": []}
    if os.path.isfile(functions_file):
        with open(functions_file, "r", encoding="utf-8") as f:
            existing_funcs = json.load(f)

    existing_switches = []
    if os.path.isfile(switches_file):
        with open(switches_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
            existing_switches = raw if isinstance(raw, list) else raw.get("switches", [])

    all_funcs = {}
    for category in ("interrupt_functions", "main_functions", "regular_functions"):
        for fn in existing_funcs.get(category, []):
            all_funcs[fn["name"]] = dict(fn)

    patch_interrupts = {}
    for item in agent_patch.get("interrupt_functions", []):
        name = item.get("name", "").strip()
        if not name:
            continue
        if name not in all_funcs:
            warnings.append(f"[WARN] interrupt_function '{name}' 在静态分析中未找到，跳过")
            continue
        patch_interrupts[name] = item

    patch_mains = set()
    for name in agent_patch.get("main_functions", []):
        name = name.strip()
        if not name:
            continue
        if name not in all_funcs:
            warnings.append(f"[WARN] main_function '{name}' 在静态分析中未找到，跳过")
            continue
        patch_mains.add(name)

    new_interrupt, new_main, new_regular = [], [], []
    for name, fn in all_funcs.items():
        fn = dict(fn)
        if name in patch_interrupts:
            fn["type"] = "interrupt"
            fn["priority"] = patch_interrupts[name]["priority"]
            fn.pop("interrupt_number", None)
            new_interrupt.append(fn)
        elif name in patch_mains:
            fn["type"] = "main"
            fn.pop("priority", None)
            fn.pop("interrupt_number", None)
            new_main.append(fn)
        else:
            fn["type"] = "regular"
            fn.pop("priority", None)
            fn.pop("interrupt_number", None)
            new_regular.append(fn)

    new_interrupt.sort(key=lambda x: x.get("priority", 999))

    with open(functions_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "interrupt_functions": new_interrupt,
                "main_functions": new_main,
                "regular_functions": new_regular,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    interrupt_names = {fn["name"] for fn in new_interrupt}
    switch_patch_map = {}
    for st in agent_patch.get("switch_targets", []):
        line = st.get("line")
        if line is None:
            continue
        targets = [t for t in st.get("targets", []) if t in interrupt_names]
        invalid = [t for t in st.get("targets", []) if t not in interrupt_names]
        if invalid:
            warnings.append(f"[WARN] switch line {line}: targets {invalid} 不在 interrupt_functions 中，跳过")
        switch_patch_map[line] = targets

    for sw in existing_switches:
        line = sw.get("line_number")
        if line in switch_patch_map:
            sw["mapped_targets"] = switch_patch_map[line]
            sw["mapped_target_functions"] = switch_patch_map[line]

    with open(switches_file, "w", encoding="utf-8") as f:
        json.dump(existing_switches, f, ensure_ascii=False, indent=2)

    priorities = {}
    for fn in new_interrupt:
        priorities[fn["name"]] = {
            "function_name": fn["name"],
            "priority": fn["priority"],
            "type": "interrupt",
            "source": "agent",
            "file_path": fn.get("file_path", ""),
            "line_number": fn.get("line_number", 0),
        }

    with open(priorities_file, "w", encoding="utf-8") as f:
        json.dump(priorities, f, ensure_ascii=False, indent=2)

    return {
        "interrupt_functions_merged": len(new_interrupt),
        "main_functions_merged": len(new_main),
        "regular_functions_inferred": len(new_regular),
        "switches_mapped": sum(1 for s in existing_switches if s.get("mapped_targets")),
        "warnings": warnings,
    }


@mcp.tool()
@_log_tool_call
def interrupt_analyze(project_path: str, mode: str = "static") -> dict:
    """静态提取中断相关语义。mode=static 适合 TestSuite/已知架构；mode=agent 用于未知架构补全。"""
    if not os.path.isdir(project_path):
        return {"status": "error", "errors": [f"project_path 不存在: {project_path!r}"]}

    analysis_path = os.path.join(project_path, "improved_interrupt_analysis")

    if mode == "agent":
        try:
            from ice_core.static_analysis.agent_analyzer import ImprovedInterruptModelAnalyzer
        except ImportError:
            return {"status": "error", "errors": ["无法导入 agent_analyzer"]}
    else:
        try:
            from ice_core.static_analysis.analyzer import ImprovedInterruptModelAnalyzer
        except ImportError:
            return {"status": "error", "errors": ["无法导入 analyzer"]}

    # mode=static: always re-run (fast, deterministic, avoids stale cache bugs)
    # mode=agent:  skip if already analyzed (may contain merged agent patch)
    should_run = (mode == "static") or (not os.path.isdir(analysis_path))
    if should_run:
        try:
            with _stdout_guarded():
                analyzer = ImprovedInterruptModelAnalyzer(project_path)
                analyzer.analyze_project(debug_mode=False)
        except Exception as e:
            return {"status": "error", "stage": "static_analysis", "errors": [str(e)]}

    result = {
        "status": "ok",
        "analysis_path": analysis_path,
        "mode": mode,
    }

    if mode == "agent":
        result["supplement_context"] = _build_supplement_context(project_path, analysis_path)
    else:
        with _stdout_guarded():
            result["postprocess"] = _run_analyzer_postprocess(analysis_path)

    return result


@mcp.tool()
@_log_tool_call
def interrupt_analyze_merge(project_path: str, agent_patch: dict) -> dict:
    """将 agent 识别结果合并回 Stage 1 产物，更新函数分类、优先级和开关目标。"""
    if not os.path.isdir(project_path):
        return {"status": "error", "errors": [f"project_path 不存在: {project_path!r}"]}

    analysis_path = os.path.join(project_path, "improved_interrupt_analysis")
    if not os.path.isdir(analysis_path):
        return {"status": "error", "errors": ["analysis_path 不存在，请先运行 interrupt_analyze"]}

    if not isinstance(agent_patch, dict):
        return {"status": "error", "errors": ["agent_patch 必须是 dict"]}

    try:
        with _stdout_guarded():
            merge_stats = _merge_agent_patch(analysis_path, agent_patch)
        with _stdout_guarded():
            postprocess = _run_analyzer_postprocess(analysis_path)
        return {
            "status": "ok",
            "analysis_path": analysis_path,
            "merge_stats": merge_stats,
            "warnings": merge_stats.get("warnings", []),
            "postprocess": postprocess,
        }
    except Exception as e:
        import traceback
        return {"status": "error", "errors": [str(e)], "traceback": traceback.format_exc()}


# ---------------------------------------------------------------------------
# IACPG 构建与查询
# ---------------------------------------------------------------------------

@mcp.tool()
@_log_tool_call
def build_interrupt_facts(project_path: str) -> dict:
    """基于 Stage 1 产物生成 interrupt_facts.json 和 interrupt_relations.json。"""
    try:
        project = _resolve_project_path(project_path)
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}

    result = _run_json_python(FACTS_SCRIPT, str(project))
    if not result["ok"]:
        return {"status": "error", "errors": [result["stderr"] or result["stdout"]], "command": result["command"]}

    return {
        "status": "ok",
        "project_path": str(project),
        "facts_dir": str(_facts_dir(project)),
        "stdout": result["stdout"],
    }


@mcp.tool()
@_log_tool_call
def build_iacpg(project_path: str) -> dict:
    """基于 interrupt facts 和 Joern 导出结果构建 iacpg.graphml。"""
    try:
        project = _resolve_project_path(project_path)
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}

    result = _run_json_python(BUILD_IACPG_SCRIPT, str(project))
    if not result["ok"]:
        return {"status": "error", "errors": [result["stderr"] or result["stdout"]], "command": result["command"]}

    return {
        "status": "ok",
        "project_path": str(project),
        "graph_path": str(_graph_path(project)),
        "stdout": result["stdout"],
    }


def _run_iacpg_query(project_path: str, subcommand: str, *extra: str) -> dict:
    project = _resolve_project_path(project_path)
    graph = _ensure_graph(project)
    result = _run_json_python(QUERY_SCRIPT, str(graph), subcommand, *extra)
    if not result["ok"]:
        return {"status": "error", "errors": [result["stderr"] or result["stdout"]], "command": result["command"]}
    return {
        "status": "ok",
        "project_path": str(project),
        "graph_path": str(graph),
        "query": subcommand,
        "output": result["stdout"],
    }


@mcp.tool()
@_log_tool_call
def iacpg_summary(project_path: str) -> dict:
    """返回 IACPG 图的节点/边标签摘要。"""
    return _run_iacpg_query(project_path, "summary")


@mcp.tool()
@_log_tool_call
def iacpg_preemptions(project_path: str) -> dict:
    """返回 IACPG 中的 INTERRUPT_PREEMPTS 关系。"""
    return _run_iacpg_query(project_path, "preemptions")


@mcp.tool()
@_log_tool_call
def iacpg_switches(project_path: str) -> dict:
    """返回 IACPG 中的 ENABLES / DISABLES 关系。"""
    return _run_iacpg_query(project_path, "switches")


@mcp.tool()
@_log_tool_call
def iacpg_variable(project_path: str, variable_name: str) -> dict:
    """返回某个共享变量在 IACPG 中的访问与潜在并发关系。"""
    return _run_iacpg_query(project_path, "var", variable_name)


# ---------------------------------------------------------------------------
# Joern 查询封装
# ---------------------------------------------------------------------------

@mcp.tool()
@_log_tool_call
def joern_import(project_path: str, project_name: str = "") -> dict:
    """把源码目录导入 Joern server 工作区，供后续 CPGQL 查询复用。"""
    try:
        project = _resolve_project_path(project_path)
        pname = project_name or project.name

        def _do():
            from ice_core.utils.joern import JoernClient
            with _stdout_guarded():
                client = JoernClient()
                reused = _reuse_existing_joern_project(client, project)
                if reused:
                    return {
                        "reused_existing": True,
                        "opened_project": reused,
                    }
                return client.import_code(str(project), pname)

        result = _run_in_thread(_do)
        return {
            "status": "ok",
            "project_path": str(project),
            "project_name": pname,
            "result": result,
        }
    except Exception as e:
        import traceback
        return {"status": "error", "errors": [str(e)], "traceback": traceback.format_exc()}


@mcp.tool()
def joern_workspace() -> dict:
    """查询当前 Joern workspace 状态。"""
    try:
        def _do():
            from ice_core.utils.joern import JoernClient
            with _stdout_guarded():
                client = JoernClient()
                return client.workspace_query()

        result = _run_in_thread(_do)
        return {"status": "ok", "result": result}
    except Exception as e:
        import traceback
        return {"status": "error", "errors": [str(e)], "traceback": traceback.format_exc()}


@mcp.tool()
@_log_tool_call
def joern_query(project_path: str, query: str, project_name: str = "", save_result: bool = False, output_file: str = "") -> dict:
    """执行任意 Joern CPGQL 查询。若项目尚未导入，则先自动导入。"""
    try:
        project = _resolve_project_path(project_path)
        pname = project_name or project.name

        def _do():
            from ice_core.utils.joern import JoernClient
            with _stdout_guarded():
                client = JoernClient()
                reused = _reuse_existing_joern_project(client, project)
                if not reused:
                    client.import_code(str(project), pname)
                return client.query(query, save_result=save_result, output_file=output_file or None)

        result = _run_in_thread(_do)
        payload = {
            "status": "ok",
            "project_path": str(project),
            "project_name": pname,
            "result": result,
        }
        if save_result:
            payload["saved_to"] = output_file or "query_result.json"
        return payload
    except Exception as e:
        import traceback
        return {"status": "error", "errors": [str(e)], "traceback": traceback.format_exc()}


@mcp.tool()
@_log_tool_call
def joern_methods(project_path: str, project_name: str = "") -> dict:
    """列出项目中的 method 名称，适合作为 OpenCode 检测前的结构扫描。"""
    query = "cpg.method.name.l"
    return joern_query(project_path=project_path, query=query, project_name=project_name)


@mcp.tool()
@_log_tool_call
def joern_calls(project_path: str, project_name: str = "") -> dict:
    """列出项目中的调用名，帮助智能体识别 enable_isr/disable_isr 等关键 API。"""
    query = "cpg.call.name.l.distinct"
    return joern_query(project_path=project_path, query=query, project_name=project_name)


@mcp.tool()
@_log_tool_call
def joern_identifiers(project_path: str, project_name: str = "") -> dict:
    """列出项目中的 identifier 名称，便于收缩共享变量候选。"""
    query = "cpg.identifier.name.l.distinct"
    return joern_query(project_path=project_path, query=query, project_name=project_name)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "__run_script__":
        script = sys.argv[2]
        sys.argv = [script, *sys.argv[3:]]
        runpy.run_path(script, run_name="__main__")
    else:
        mcp.run()
