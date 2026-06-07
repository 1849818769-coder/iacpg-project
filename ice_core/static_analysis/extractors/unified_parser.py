"""
统一中断信息解析器 (Unified Interrupt Parser)

输入：
  - 智能体 (InterruptInfoAgent) 返回的统一 JSON 结构（新路径）
  - 或旧版三文件格式（向后兼容路径）

输出接口与旧版提取器完全兼容：
  - self.interrupt_functions   ← FunctionIdentifier.identify_interrupt_functions
  - self.main_functions        ← FunctionIdentifier.identify_main_functions
  - self.regular_functions     ← FunctionIdentifier.identify_regular_functions
  - self.interrupt_priorities  ← InterruptPriorityExtractor.build_interrupt_priorities
  - self.interrupt_switches    ← InterruptSwitchExtractor.extract_interrupt_switches

"""

import json
import os
from typing import List, Dict, Any, Optional

from .unified_loader import (
    INTERRUPT_FUNCTION_PATTERNS,
    INTERRUPT_FUNCTION_PATTERN_ENTRIES,
    INTERRUPT_SWITCH_PATTERNS,
    INTERRUPT_PRIORITY_PATTERNS,
    _RUN_TASKS_RE,
    _RUN_PRIORITY_RE
)

# ─────────────────────────────────────────────────────────────────────────────
# main 函数识别正则（各架构通用，无需区分）
# ─────────────────────────────────────────────────────────────────────────────

MAIN_FUNCTION_PATTERNS: List[str] = [
    # 标准 C：int main(...)
    r'int\s+(.*main.*)\s*\([^)]*\)\s*\{',
    # 嵌入式变体：void main(...)（部分 RTOS/裸机环境不返回）
    r'void\s+(.*main.*)\s*\([^)]*\)\s*\{',
]

# ─────────────────────────────────────────────────────────────────────────────
# 普通函数识别正则（各架构通用，无需区分）
# ─────────────────────────────────────────────────────────────────────────────

REGULAR_FUNCTION_PATTERNS: List[str] = []



# ─────────────────────────────────────────────────────────────────────────────
# 核心解析器
# ─────────────────────────────────────────────────────────────────────────────

def _detect_file_architectures(content: str) -> set[str]:
    import re
    arches: set[str] = set()
    if 'ISR(' in content or 'sei(' in content or 'cli(' in content:
        arches.add('AVR')
    if '__interrupt' in content or '__enable_interrupt' in content or '__disable_interrupt' in content:
        arches.add('MSP430')
    if '__attribute__' in content and 'interrupt(' in content:
        if any(v in content for v in ['_VECTOR', 'TIMER', 'PORT', 'WDT', 'ADC', 'COM', 'UART', 'SCI', 'SPI', 'I2C']):
            arches.add('MSP430')
    if ('PLIC_' in content
            or ('Machine' in content and 'IRQn' in content)
            or re.search(r'\b(?:Machine|Supervisor|External|Timer|Software)\w*IRQHandler\b', content)):
        arches.add('RISC-V')
    if 'NVIC_' in content or 'HAL_NVIC_' in content:
        arches.add('ARM')
    if 'enable_isr(' in content or 'disable_isr(' in content:
        arches.add('TestSuite')
    if not arches:
        arches.add('Generic')
    return arches


class UnifiedInterruptParser:
    """
    统一中断信息解析器。

    支持两种输入格式：
      1. 智能体统一 JSON（新格式）
      2. 旧版三文件格式（向后兼容）

    使用示例（新格式）:
        parser = UnifiedInterruptParser()
        parser.from_agent_result(agent_result, file_path)
        funcs = parser.interrupt_functions

    使用示例（旧格式兼容）:
        parser = UnifiedInterruptParser.load_from_legacy_paths(
            functions_path, priorities_path, switches_path
        )
    """

    # 暴露模式常量，下游提取器可直接引用
    INTERRUPT_FUNCTION_PATTERNS = INTERRUPT_FUNCTION_PATTERNS
    MAIN_FUNCTION_PATTERNS = MAIN_FUNCTION_PATTERNS
    REGULAR_FUNCTION_PATTERNS = REGULAR_FUNCTION_PATTERNS

    def __init__(self):
        self.interrupt_functions:  List[Dict[str, Any]]  = []
        self.main_functions:       List[Dict[str, Any]]  = []
        self.regular_functions:    List[Dict[str, Any]]  = []
        self.interrupt_switches:   List[Dict[str, Any]]  = []
        self.interrupt_priorities: Dict[str, Dict[str, Any]] = {}

    # ── 方式 1：解析智能体统一 JSON ──────────────────────────────────────────

    def from_agent_result(
        self,
        agent_result: Dict[str, Any],
        file_path: str = "",
    ) -> "UnifiedInterruptParser":
        """
        从智能体返回的统一 JSON 解析。

        Args:
            agent_result: 符合统一格式的字典（含 "functions" 和 "interrupt_switches" 键）
            file_path:    当前源文件路径，用于填充未提供 file_path 的条目
        """
        self._reset()

        for func in agent_result.get("functions", []):
            entry = self._normalize_function(func, file_path)
            ftype = entry["type"]
            if ftype == "interrupt":
                self.interrupt_functions.append(entry)
                self.interrupt_priorities[entry["name"]] = self._make_priority_entry(entry)
            elif ftype == "main":
                self.main_functions.append(entry)
                self.interrupt_priorities[entry["name"]] = self._make_priority_entry(entry)
            else:
                self.regular_functions.append(entry)

        for sw in agent_result.get("interrupt_switches", []):
            self.interrupt_switches.append(self._normalize_switch(sw, file_path))

        return self

    # ── 方式 2：向后兼容旧版三文件格式 ──────────────────────────────────────

    def from_legacy_dicts(
        self,
        functions_json: Dict[str, Any],
        priorities_json: Dict[str, Any],
        switches_json: List[Dict[str, Any]],
    ) -> "UnifiedInterruptParser":
        """
        从旧版三个已解析的 dict / list 加载。

        Args:
            functions_json:  functions.json 内容
            priorities_json: interrupt_priorities.json 内容
            switches_json:   interrupt_switches.json 内容
        """
        self._reset()
        self.interrupt_functions  = functions_json.get("interrupt_functions", [])
        self.main_functions       = functions_json.get("main_functions", [])
        self.regular_functions    = functions_json.get("regular_functions", [])
        self.interrupt_priorities = priorities_json if isinstance(priorities_json, dict) else {}
        self.interrupt_switches   = switches_json   if isinstance(switches_json, list)  else []
        return self

    @classmethod
    def load_from_legacy_paths(
        cls,
        functions_path: str,
        priorities_path: str,
        switches_path: str,
    ) -> "UnifiedInterruptParser":
        """从旧版三个 JSON 文件路径加载（向后兼容）"""
        parser = cls()
        with open(functions_path,  "r", encoding="utf-8") as f:
            functions_json  = json.load(f)
        with open(priorities_path, "r", encoding="utf-8") as f:
            priorities_json = json.load(f)
        with open(switches_path,   "r", encoding="utf-8") as f:
            switches_json   = json.load(f)
        return parser.from_legacy_dicts(functions_json, priorities_json, switches_json)

    # ── 方式 3：静态分析结构 + 智能体最小 JSON 合并（推荐路径） ──────────────

    def from_static_and_agent(
        self,
        static_functions: Dict[str, List[Dict[str, Any]]],
        agent_minimal: Dict[str, Any],
        file_path: str = "",
    ) -> "UnifiedInterruptParser":
        """
        合并静态分析函数结构 + 智能体最小 JSON。

        静态分析提供：function_body / function_definition / line_number / architecture
        智能体提供  ：ISR 分类 / priority / interrupt_number / 中断开关

        Args:
            static_functions: FunctionIdentifier.identify_all_functions() 的输出
                              {"interrupt_functions": [...], "main_functions": [...],
                               "regular_functions": [...]}
            agent_minimal:    InterruptInfoAgent.analyze_interrupts() 的输出
                              {"isrs": [...], "switches": [...]}
            file_path:        当前源文件路径（用于填充缺失字段）
        """
        self._reset()

        # 构建 ISR 查找表
        isr_map: Dict[str, Dict[str, Any]] = {
            isr["name"]: isr for isr in agent_minimal.get("isrs", [])
        }
        agent_has_isrs = bool(isr_map)

        all_static = (
            static_functions.get("interrupt_functions", [])
            + static_functions.get("main_functions", [])
            + static_functions.get("regular_functions", [])
        )

        seen_names: set = set()
        for func in all_static:
            fname = func.get("name", "")
            if fname in seen_names:
                continue
            seen_names.add(fname)

            static_type = func.get("type", "regular")

            if agent_has_isrs:
                # 以智能体分类为准
                if fname in isr_map:
                    isr_info = isr_map[fname]
                    entry = dict(func)
                    entry["type"] = "interrupt"
                    entry["priority"] = isr_info.get("priority", 1)
                    entry["interrupt_number"] = isr_info.get("interrupt_number")
                    entry.setdefault("file_path", file_path)
                    self.interrupt_functions.append(entry)
                    self.interrupt_priorities[fname] = self._make_priority_entry(entry)
                elif static_type == "main":
                    entry = dict(func)
                    entry.setdefault("priority", 0)
                    entry.setdefault("file_path", file_path)
                    self.main_functions.append(entry)
                    self.interrupt_priorities[fname] = self._make_priority_entry(entry)
                else:
                    entry = dict(func)
                    entry["type"] = "regular"
                    entry.setdefault("priority", 0)
                    entry.setdefault("file_path", file_path)
                    self.regular_functions.append(entry)
            else:
                # 智能体无结果：退回静态分析类型
                entry = dict(func)
                entry.setdefault("file_path", file_path)
                if static_type == "interrupt":
                    self.interrupt_functions.append(entry)
                    self.interrupt_priorities[fname] = self._make_priority_entry(entry)
                elif static_type == "main":
                    entry.setdefault("priority", 0)
                    self.main_functions.append(entry)
                    self.interrupt_priorities[fname] = self._make_priority_entry(entry)
                else:
                    entry.setdefault("priority", 0)
                    self.regular_functions.append(entry)

        # 处理智能体返回的中断开关
        for sw in agent_minimal.get("switches", []):
            self.interrupt_switches.append(self._normalize_switch(sw, file_path))

        return self

    # ── 静态函数提取（供 analyzer.py 调用） ─────────────────────────────────

    @staticmethod
    def _extract_function_definition_and_body(content: str, start_pos: int) -> tuple:
        lines = content[:start_pos].split('\n')
        func_def_start = 0
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith('//') and not line.startswith('/*'):
                func_def_start = sum(len(lines[j]) + 1 for j in range(i))
                break
        
        brace_start = content.find('{', start_pos)
        if brace_start == -1:
            return "", ""
        
        brace_count = 1
        pos = brace_start + 1
        
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{': brace_count += 1
            elif content[pos] == '}': brace_count -= 1
            pos += 1
            
        if brace_count == 0:
            func_def_lines = content[func_def_start:brace_start].strip().split('\n')
            func_def = func_def_lines[-1].strip() if func_def_lines else ""
            return func_def, content[brace_start:pos]
            
        return "", ""

    @staticmethod
    def _detect_architecture(func_name: str) -> str:
        if func_name.endswith('_vect'):
            return "AVR"
        if func_name.endswith('_ISR') or func_name.startswith('PORT') or func_name.startswith('TIMER'):
            return "MSP430"
        if 'IRQHandler' in func_name and (
            func_name.startswith('Machine')
            or func_name.startswith('Supervisor')
            or func_name.startswith('External')
            or func_name.startswith('Timer')
            or func_name.startswith('Software')
        ):
            return "RISC-V"
        # ARM CMSIS 风格：任意外设名 + IRQHandler，但排除 RISC-V 保留前缀
        # 注意：UART0/SPI1 等外设 handler 在标准 RISC-V 中不应单独存在，
        # 若出现在代码中通常是 ARM 风格写法或已通过 MachineExternal dispatch 改造
        if 'IRQHandler' in func_name or '_IRQHandler' in func_name or 'IRQn' in func_name:
            return "ARM"
        if 'Interrupt' in func_name:
            return "PIC"
        if 'exception_handler' in func_name:
            return "RISC-V"
        if '_vector' in func_name:
            return "MSP430"
        return "Generic"

    @staticmethod
    def extract_static_priorities(
        content: str, file_path: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """
        扫描文件中的显式优先级设置，返回 {function_name_or_irqn: info} 映射。

        支持：
          - NVIC_SetPriority(IRQn, priority)
          - HAL_NVIC_SetPriority(IRQn, preemptPriority, subPriority)
          - // RUN: ... -tasks=f1,f2 -priority=0,1,2
        """
        import re
        result: Dict[str, Dict[str, Any]] = {}
        detected_arches = _detect_file_architectures(content)

        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            # RUN 注释：-tasks=f1,f2 -priority=0,1,2（顺序不限）
            if _RUN_TASKS_RE in line or "-tasks=" in line:
                tm = re.search(_RUN_TASKS_RE, line)
                pm = re.search(_RUN_PRIORITY_RE, line)
                if tm and pm:
                    tasks = tm.group(1).split(",")
                    priorities = pm.group(1).split(",")
                    for fname, pval in zip(tasks, priorities):
                        fname = fname.strip()
                        if fname:
                            result[fname] = {
                                "priority": int(pval.strip()),
                                "source": "run_comment",
                                "architecture": "Generic",
                                "line_number": line_no,
                                "file_path": file_path,
                            }
                continue

            # NVIC / HAL / PLIC / FreeRTOS 调用
            for pat, source, arch in INTERRUPT_PRIORITY_PATTERNS:
                if arch not in detected_arches and arch != 'Generic':
                    continue
                m = re.search(pat, line)
                if m:
                    irqn = m.group(1).strip()
                    priority = int(m.group(2).strip())
                    result[irqn] = {
                        "priority": priority,
                        "source": source,
                        "architecture": arch,
                        "line_number": line_no,
                        "file_path": file_path,
                    }

        return result

    @staticmethod
    def extract_static_functions(
        content: str, file_path: str = "", ast_functions: Optional[List[dict]] = None
    ) -> dict:
        import re
        result = {"interrupt_functions": [], "main_functions": [], "regular_functions": []}
        identified_names = set()
        detected_arches = _detect_file_architectures(content)

        # 预先扫描文件中的显式优先级设置
        priority_map = UnifiedInterruptParser.extract_static_priorities(content, file_path)

        def resolve_priority_info(fname: str) -> tuple[int, Optional[int]]:
            if fname in priority_map:
                return priority_map[fname]["priority"], None

            candidate_keys = []
            if fname.endswith('_IRQHandler'):
                base = fname[:-len('_IRQHandler')]
                candidate_keys.extend([f'{base}_IRQn', f'{base}IRQn'])
            elif fname.endswith('IRQHandler'):
                base = fname[:-len('IRQHandler')]
                candidate_keys.extend([f'{base}_IRQn', f'{base}IRQn'])

            for key in candidate_keys:
                if key in priority_map:
                    return priority_map[key]["priority"], None

            num_m = re.search(r'_(\d+)$', fname)
            interrupt_number = int(num_m.group(1)) if num_m else None
            priority = interrupt_number if interrupt_number is not None else 1
            return priority, interrupt_number

        # Interrupt functions
        for pattern, arch in INTERRUPT_FUNCTION_PATTERN_ENTRIES:
            if arch not in detected_arches and arch != 'Generic':
                continue
            for match in re.finditer(pattern, content, re.MULTILINE):
                fname = match.group(1)
                if fname in identified_names:
                    continue
                fline = content[:match.start()].count('\n') + 1
                fdef, fbody = UnifiedInterruptParser._extract_function_definition_and_body(content, match.start())
                # 优先级来源：① 显式设置（priority_map / IRQn 映射）② 函数名尾部数字 ③ 默认 1
                priority, interrupt_number = resolve_priority_info(fname)
                result["interrupt_functions"].append({
                    "name": fname, "file_path": file_path, "line_number": fline,
                    "function_definition": fdef, "function_body": fbody,
                    "type": "interrupt", "priority": priority,
                    "interrupt_number": interrupt_number,
                    "architecture": UnifiedInterruptParser._detect_architecture(fname)
                })
                identified_names.add(fname)

        # Fallback for callback/dispatch-style handlers: if the file exposes exactly one
        # interrupt priority configuration and exactly one interrupt function, bind them.
        if len(result["interrupt_functions"]) == 1 and len(priority_map) == 1:
            sole_interrupt = result["interrupt_functions"][0]
            sole_priority = next(iter(priority_map.values()))
            sole_interrupt["priority"] = sole_priority.get("priority", sole_interrupt.get("priority", 1))
            if sole_interrupt.get("interrupt_number") is None:
                sole_interrupt["interrupt_number"] = sole_priority.get("interrupt_number")

        # Main functions
        for pattern in MAIN_FUNCTION_PATTERNS:
            for match in re.finditer(pattern, content, re.MULTILINE):
                fname = match.group(1)
                fline = content[:match.start()].count('\n') + 1
                fdef, fbody = UnifiedInterruptParser._extract_function_definition_and_body(content, match.start())
                result["main_functions"].append({
                    "name": fname, "file_path": file_path, "line_number": fline,
                    "function_definition": fdef, "function_body": fbody,
                    "type": "main", "priority": 0
                })
                identified_names.add(fname)

        # Regular functions
        if ast_functions is not None:
            for func in ast_functions:
                fname = func.get("func_name", "")
                if not fname or fname in identified_names or "main" in fname.lower():
                    continue
                func_code = func.get("func_code", "")
                fline = func.get("start_line", 0)
                
                brace_start = func_code.find('{')
                if brace_start != -1:
                    fdef = func_code[:brace_start].strip()
                    fbody = func_code[brace_start:]
                else:
                    fdef, fbody = "", func_code
                    
                result["regular_functions"].append({
                    "name": fname, "file_path": file_path, "line_number": fline,
                    "function_definition": fdef, "function_body": fbody,
                    "type": "regular", "priority": 0
                })
                identified_names.add(fname)
        else:
            for pattern in REGULAR_FUNCTION_PATTERNS:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    fname = match.group(1).strip()
                    if fname in identified_names or "main" in fname.lower() or fname in ['if', 'for', 'while', 'switch', 'catch']:
                        continue
                    fline = content[:match.start()].count('\n') + 1
                    fdef, fbody = UnifiedInterruptParser._extract_function_definition_and_body(content, match.start())
                    result["regular_functions"].append({
                        "name": fname, "file_path": file_path, "line_number": fline,
                        "function_definition": fdef, "function_body": fbody,
                        "type": "regular", "priority": 0
                    })
                    identified_names.add(fname)

        return result

    @staticmethod
    def extract_static_switches(
        content: str, file_path: str = ""
    ) -> List[Dict[str, Any]]:
        """
        静态扫描中断开关操作（enable / disable）。

        追踪当前所在函数名（基于大括号深度），识别常见的中断使能/禁止调用。
        """
        import re
        results: List[Dict[str, Any]] = []
        detected_arches = _detect_file_architectures(content)
        lines = content.split("\n")

        current_func = ""
        brace_depth = 0
        all_func_patterns = (
            INTERRUPT_FUNCTION_PATTERNS
            + MAIN_FUNCTION_PATTERNS
            + REGULAR_FUNCTION_PATTERNS
        )

        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()

            matched_func_def = False
            # 在深度为 0 时检测函数定义（新函数开始）
            if brace_depth == 0:
                for pat in all_func_patterns:
                    m = re.search(pat, line)
                    if m:
                        current_func = m.group(1)
                        matched_func_def = True
                        break

            open_b  = line.count("{")
            close_b = line.count("}")
            brace_depth += open_b - close_b

            # 跳过注释行 / 文件级声明（brace_depth==0 说明不在任何函数体内）
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if brace_depth == 0 or matched_func_def:
                continue

            for sw_pat, operation, arch, has_target in INTERRUPT_SWITCH_PATTERNS:
                if arch not in detected_arches and arch != 'Generic':
                    continue
                m = re.search(sw_pat, line)
                if m:
                    target = m.group(1).strip() if has_target else ""
                    results.append({
                        "line_number":             line_no,
                        "operation":               operation,
                        "target":                  target,
                        "code":                    stripped,
                        "file_path":               file_path,
                        "function":                current_func,
                        "mapped_targets":          [],
                        "mapped_target_functions": [],
                        "architecture":            arch,
                    })

        return results

    def to_functions_json(self) -> Dict[str, Any]:
        """导出为旧版 functions.json 格式"""
        return {
            "interrupt_functions": self.interrupt_functions,
            "main_functions":      self.main_functions,
            "regular_functions":   self.regular_functions,
        }

    def to_priorities_json(self) -> Dict[str, Any]:
        """导出为旧版 interrupt_priorities.json 格式"""
        return self.interrupt_priorities

    def to_switches_json(self) -> List[Dict[str, Any]]:
        """导出为旧版 interrupt_switches.json 格式"""
        return self.interrupt_switches

    def to_unified_json(self) -> Dict[str, Any]:
        """导出为统一 JSON 格式（可直接传回给智能体或持久化）"""
        all_functions = (
            self.interrupt_functions
            + self.main_functions
            + self.regular_functions
        )
        funcs_out = [
            {
                "name":                f.get("name", ""),
                "type":                f.get("type", "regular"),
                "priority":            f.get("priority", 0),
                "interrupt_number":    f.get("interrupt_number"),
                "line_number":         f.get("line_number", 0),
                "file_path":           f.get("file_path", ""),
                "function_definition": f.get("function_definition", ""),
                "function_body":       f.get("function_body", ""),
                "architecture":        f.get("architecture", "Generic"),
            }
            for f in all_functions
        ]
        return {
            "functions":          funcs_out,
            "interrupt_switches": self.interrupt_switches,
        }

    # ── 内部辅助 ─────────────────────────────────────────────────────────────

    def _reset(self):
        self.interrupt_functions  = []
        self.main_functions       = []
        self.regular_functions    = []
        self.interrupt_switches   = []
        self.interrupt_priorities = {}

    def _normalize_function(
        self, func: Dict[str, Any], default_file_path: str
    ) -> Dict[str, Any]:
        return {
            "name":                func.get("name", ""),
            "file_path":           func.get("file_path", default_file_path),
            "line_number":         func.get("line_number", 0),
            "function_definition": func.get("function_definition", ""),
            "function_body":       func.get("function_body", ""),
            "type":                func.get("type", "regular"),
            "priority":            func.get("priority", 0),
            "interrupt_number":    func.get("interrupt_number"),
            "architecture":        func.get("architecture", "Generic"),
        }

    def _normalize_switch(
        self, sw: Dict[str, Any], default_file_path: str
    ) -> Dict[str, Any]:
        mapped = (
            sw.get("mapped_targets")
            or sw.get("mapped_target_functions")
            or []
        )
        return {
            "line_number":           sw.get("line_number", 0),
            "operation":             sw.get("operation", ""),
            "target":                sw.get("target", ""),
            "code":                  sw.get("code", ""),
            "file_path":             sw.get("file_path", default_file_path),
            "function":              sw.get("function", ""),
            "mapped_targets":        mapped,
            "mapped_target_functions": mapped,
            "architecture":          sw.get("architecture", "Generic"),
        }

    def _make_priority_entry(self, func: Dict[str, Any]) -> Dict[str, Any]:
        ftype = func.get("type", "regular")
        return {
            "function_name":   func["name"],
            "priority":        func.get("priority", 1 if ftype == "interrupt" else 0),
            "type":            ftype,
            "source":          "agent" if ftype == "interrupt" else "default",
            "interrupt_number": func.get("interrupt_number"),
            "priority_code":   None,
            "priority_comment": None,
            "file_path":       func.get("file_path", ""),
            "line_number":     func.get("line_number", 0),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数（向后兼容旧版 function_id / priority / switch 的便捷函数接口）
# ─────────────────────────────────────────────────────────────────────────────

def parse_agent_result(
    agent_result: Dict[str, Any], file_path: str = ""
) -> UnifiedInterruptParser:
    """便捷函数：从智能体结果构造解析器"""
    return UnifiedInterruptParser().from_agent_result(agent_result, file_path)


def load_legacy(
    functions_path: str, priorities_path: str, switches_path: str
) -> UnifiedInterruptParser:
    """便捷函数：从旧版三文件路径构造解析器"""
    return UnifiedInterruptParser.load_from_legacy_paths(
        functions_path, priorities_path, switches_path
    )
