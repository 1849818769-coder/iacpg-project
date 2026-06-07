"""
中断信息提取智能体 (InterruptInfoAgent) — OpenCode 模式

⚠️ LLM 语义分析已委托给 OpenCode AI 通过 SKILL.md 完成。
   本模块仅作占位接口，始终返回空结果。

流程：
  1. 静态分析 (UnifiedInterruptParser) 提取候选函数结构（函数体/定义/行号）
  2. 工具 (interrupt_analyze.ts) 将候选函数完整返回给 OpenCode
  3. OpenCode AI 按照 SKILL.md 指令进行语义识别：
       - 判断哪些函数是 ISR（命名约定 / 属性标注 / 向量表引用）
       - 从 NVIC_SetPriority 调用推断优先级
       - 识别中断开关操作（NVIC_EnableIRQ / sei / cli 等）
  4. OpenCode 直接输出最终增强 JSON，无需再调用外部 LLM
"""

from typing import Dict, Any, List, Optional


class InterruptInfoAgent:
    """
    中断信息提取智能体（OpenCode 委托模式）。

    LLM 分析已由 OpenCode AI 自身承担，本类始终返回空占位，
    静态分析结果通过工具返回值传递给 OpenCode 进行语义增强。
    """

    def __init__(
        self,
        api_key:  Optional[str] = None,
        base_url: Optional[str] = None,
        model:    Optional[str] = None,
    ):
        # 无需初始化任何 LLM 客户端
        pass

    def analyze_interrupts(
        self,
        content: str,
        file_path: str,
        candidate_functions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        返回空占位结果。

        ISR 分类、优先级推断和中断开关识别由 OpenCode AI 在工具调用返回后完成，
        依据 .opencode/skill/interrupt-analysis/SKILL.md 中的指令执行。
        """
        return {"isrs": [], "switches": []}

