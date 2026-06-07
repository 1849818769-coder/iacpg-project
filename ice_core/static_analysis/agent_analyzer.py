#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 模式分析器

与 analyzer.py 的区别：
- 跳过基于正则关键字的 ISR / main 函数分类
- 所有函数统一放入 regular_functions，分类留给 agent patch 决定
- 跳过 interrupt_priorities 生成和 switch mapped_targets 映射
  （这两项由 interrupt_analyze_merge 工具在 patch 合并后生成）

使用场景：
  static 模式无法识别 ISR（无标准关键字）时，由 MCP interrupt_analyze(mode="agent")
  调用，产出供 agent 阅读并填写 patch 的中间结果。
"""

from ice_core.static_analysis.analyzer import ImprovedInterruptModelAnalyzer
from ice_core.static_analysis.extractors.unified_parser import UnifiedInterruptParser


class AgentInterruptModelAnalyzer(ImprovedInterruptModelAnalyzer):
    """Agent 模式：所有函数均归入 regular_functions，分类由 agent patch 完成"""

    def _analyze_single_file(self, file_path: str, debug_mode: bool = False) -> dict:
        """与父类相同，但将 interrupt / main 函数全部移入 regular_functions"""
        result = super()._analyze_single_file(file_path, debug_mode)

        # 合并 interrupt / main → regular，清空前两者
        merged = (
            result.get("interrupt_functions", [])
            + result.get("main_functions", [])
            + result.get("regular_functions", [])
        )
        for fn in merged:
            fn["type"] = "regular"

        result["interrupt_functions"] = []
        result["main_functions"] = []
        result["regular_functions"] = merged
        return result

    def _post_process_analysis(self):
        """跳过 ISR 优先级生成和开关映射；其余后处理保留"""
        self._deduplicate_regular_functions()
        self._identify_shared_variables()
        self._build_function_call_graph()
        # 不调用 _build_interrupt_priorities() 和 _map_interrupt_switch_targets()
        # 这两项由 interrupt_analyze_merge 在 agent patch 合并后统一生成


# 与父类保持相同的对外名称，方便 server.py 统一 import
ImprovedInterruptModelAnalyzer = AgentInterruptModelAnalyzer
