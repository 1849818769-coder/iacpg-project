---
name: defect-detection-cpg
description: Agent(CPG) 基线配置——仅使用 Joern CPG 查询对源码直接进行四类缺陷并行判定，不使用任何预处理产物，不构建 IACPG。用于 RQ2/RQ3 对比实验。
---

# CPG-Only 混合缺陷检测器（基线）

核心要求：
- 同一测试用例必须并行检查四类缺陷：`atomicity_violation`、`interrupt_aware_div_zero`、`interrupt_aware_array_oob`、`multiword_data_race`。
- 允许一个用例同时命中多个缺陷类型（多标签）。
- **最终结果必须落盘到 `<case>/improved_interrupt_analysis/`**，至少包含：
  - `detection_result_cpg.json`
  - `detection_report_cpg.md`

---

## 严格信息隔离约束（实验公平性要求）

本配置是与 IACPG 完整流程对比的**受控基线**。为保证对比实验有效性：

**禁止读取 `<case>/improved_interrupt_analysis/` 目录下的任何文件**，包括但不限于：
- `functions.json`、`shared_variables.json`、`variable_operations.json`（Stage 1 产物）
- `interrupt_priorities.json`、`interrupt_switches.json`、`global_variables.json`（Stage 1 产物）
- `interrupt_facts/`（Stage 2 产物）
- `iacpg_artifacts/`（Stage 3 产物）
- 任何已有的 `detection_result*.json`、`detection_report*.md`
- 任何已有的 `tool_call_log*.jsonl`、`claude_run*.log`

**额外禁止读取任何历史结果或备份文件**，包括但不限于：
- 任意路径下的 `*_backup*` 文件
- `results/cpg_backups/` 目录下的任何归档文件
- 其他用例目录中的 `detection_result*`、`detection_report*`、`tool_call_log*`、`claude_run*.log`

**禁止调用任何预处理或 IACPG 相关工具**：
- `interrupt_analyze`、`interrupt_analyze_merge`
- `build_interrupt_facts`、`build_iacpg`
- `iacpg_summary`、`iacpg_preemptions`、`iacpg_switches`、`iacpg_variable`

### 源码阅读

- ✅ **允许**：读取源码以了解文件结构、辅助构造 CPGQL 查询语句。
- ❌ **禁止**：将源码阅读中获得的信息直接作为缺陷判定的证据（所有证据必须有对应的 CPG 查询结果支撑）。
- ❌ **禁止**：即使源码表面上"看起来明显有缺陷"，若无法由 `joern_*` 查询结果直接支撑，也不得判 `yes`。

---

## 可用 MCP 工具（server: `ice-interrupt-analyzer`）

### Joern 查询（唯一合法信息来源）
- `joern_import` — 导入源码到 Joern
- `joern_workspace` — 查询工作区状态
- `joern_methods` — 获取函数/方法列表
- `joern_calls` — 获取函数调用关系
- `joern_identifiers` — 获取标识符列表
- `joern_query` — 执行自定义 CPGQL 查询

---

## 总流程（必须执行）

1. **导入源码到 Joern**
   - `joern_import(project_path=<case_path>)`
   - 若已导入可跳过，直接进入查询

2. **CPG 查询收集所有证据**（以下查询均需执行）
   - `joern_methods` — 识别函数列表，推断哪些是 ISR（命名规范：`IRQHandler`、`ISR_`、`__vector_`等）
   - `joern_calls` — 获取调用关系，识别中断使能/禁用 API（`__enable_irq`、`__disable_irq`、`NVIC_EnableIRQ`、`sei`、`cli` 等）
   - `joern_identifiers` — 获取标识符，识别全局变量候选
   - `joern_query` — 按需查询：
     - 全局变量的跨函数读写访问
     - 数组访问及其索引表达式
     - 除法操作及其分母表达式
     - 多字长变量（64位类型、`_high`/`_low` 配对等）
     - 条件判断与后续使用之间的控制流

3. **基于 CPG 查询结果推断以下信息**（不得借助预处理产物）
   - ISR 函数集合：基于 `joern_*` 可直接观察到的命名模式（`IRQHandler`、`ISR_`、`__vector_` 等）、属性、注册调用或显式代码结构识别；不得靠架构常识自由补全
   - 共享变量（被 ISR 和非 ISR 函数双方访问的全局变量）
   - 中断开关保护区域（是否存在 disable/enable 包围的临界区）
   - 抢占窗口（guard check 与实际使用之间的代码区间）

4. **并行执行四类检查**
   - 原子性违反检查
   - 中断感知除零检查
   - 中断感知数组越界检查
   - 多字长数据竞争检查

5. **写回最终结果**
   - `<case>/improved_interrupt_analysis/detection_result_cpg.json`
   - `<case>/improved_interrupt_analysis/detection_report_cpg.md`
   - 不得删除、覆盖、重命名或清空任何现有的 IACPG 结果文件（如 `detection_result.json`、`detection_report.md`、`tool_call_log.jsonl`、`claude_run_iacpg.log`）。

---

## 四类缺陷确认条件

> 本配置使用与 IACPG 完整版相同的高层判定框架（5 条件结构），但只能基于 `joern_*` 查询可直接观察的证据确认缺陷。当 CPG 证据不足以直接支撑某个条件时，优先判 `no`。

### A. 原子性违反 `atomicity_violation`

**确认条件（全部满足）**：
1. 至少两个中断相关上下文可交错（如 main/task 与 ISR）。
2. 访问同一共享状态（全局/静态变量、字段或等价逻辑状态）。
3. 至少一侧有写。
4. 主流程对共享状态存在可被 CPG 查询直接证实的**易受攻击的依赖模式**，例如：
   - check-then-use（先检查共享状态，后基于检查结果执行依赖操作）
   - read-modify-write（读-改-写序列）
   - 两次分离的读取之间存在可被中断的窗口
   （仅单次读且无可观察的语义依赖时，倾向 `no`。）
5. 脆弱窗口未被显式的 disable/enable 对完整包围保护。判断保护范围时，只能基于代码中可观察的 disable/enable 调用位置，不得推断选择性屏蔽是否仍允许其他 ISR 抢占。

### B. 中断感知除零 `interrupt_aware_div_zero`

**确认条件（全部满足）**：
1. 分母（或等效步长）来自共享状态。
2. 某处有非零检查或安全条件。
3. 检查与除法（或取模）之间存在可抢占窗口——需要代码结构和 Joern 查询直接支持；若仅能靠架构常识或自由推理补全，则判 `no`。
4. ISR 可将该共享状态改为 0 或导致无效除法的值。
5. 存在真实除法或取模汇点。

### C. 中断感知数组越界 `interrupt_aware_array_oob`

**确认条件（全部满足）**：
1. 数组索引或界限由共享状态提供或派生。
2. 某处有边界检查或索引计算。
3. 检查与数组访问之间存在可抢占窗口——需要代码结构和 Joern 查询直接支持；若仅能靠架构常识或自由推理补全，则判 `no`。
4. ISR 可改变索引或驱动越界的共享状态。
5. 存在具体数组访问汇点（读或写）。

### D. 多字长数据竞争 `multiword_data_race`

**确认条件（全部满足）**：
1. 变量是**多字长类型**（位宽 > 平台字宽），或存在多字配对变量（`_high` + `_low` 等模式）。
2. 变量被**主程序路径与 ISR 双方访问**（至少一方有写）。
3. 存在**可抢占窗口**：须看到明确的多步访问证据（如多条赋值语句、拆分组装操作），不能仅凭"可能被中断"就确认。
4. 访问**未受显式 disable/enable 对保护**。

**证据要求（支撑第 3 条）**：须有 `joern_*` 查询结果直接支撑多步访问的存在，不得靠自由推理补全。

**与 `atomicity_violation` 的区别**（与完整版相同）：`atomicity_violation` 关注 RMW 序列被中断分割（软件层面）；`multiword_data_race` 关注单次访问跨越原子边界（硬件层面）。

---

## 最终输出格式

文件名带 `_cpg` 后缀，**JSON schema 必须严格遵守**：

- `detection_result_cpg.json`：

```json
{
  "case": "<case_path>",
  "verdict": "single-label|multi-label|no_bug",
  "hit_types": ["atomicity_violation"],
  "results": {
    "atomicity_violation": {
      "conclusion": "yes|no",
      "shared_variables": [],
      "triple_window": {"op1": "...", "interrupt": "...", "op3": "..."},
      "graph_evidence": [],
      "source_locations": {}
    },
    "interrupt_aware_div_zero": {"conclusion": "yes|no", "reason": "..."},
    "interrupt_aware_array_oob": {"conclusion": "yes|no", "reason": "..."},
    "multiword_data_race": {"conclusion": "yes|no", "reason": "..."}
  }
}
```

- `detection_report_cpg.md`：人类可读，必须包含：

```markdown
# 缺陷检测报告（CPG-Only 基线）

## 测试用例
- 用例路径：`<case_path>`
- 检测结论：`single-label` / `multi-label` / `no_bug`
- 命中类型：`[<hit_types>]`

## 分类结果表

| 缺陷类型 | 结论 | 共享变量 | 三元窗口 (op1, interrupt, op3) | 关键证据 |
|---|---|---|---|---|
| atomicity_violation | yes/no | ... | (...) | ... |
| interrupt_aware_div_zero | yes/no | ... | (...) | ... |
| interrupt_aware_array_oob | yes/no | ... | (...) | ... |
| multiword_data_race | yes/no | ... | (...) | ... |

## 关键证据详情

（对每个 conclusion=yes 的缺陷类型，列出 CPG 查询证据 + 源码位置）

## 被拒绝候选与理由

（对每个 conclusion=no 的缺陷类型，说明缺少哪个确认条件）
```

**结论定义**：
- `yes` = 满足所有确认条件，确认缺陷存在
- `no` = 缺少至少一个关键条件，缺陷不成立
- `uncertain` = （仅在极少数无法明确判断时使用，优先给 no）

要求：
- `关键证据` 至少包含一个 CPG 查询证据 + 一个源码位置（或 `N/A` + 原因）。
- 若无法精确行号可写 `N/A`，但必须解释被拒绝的理由。

---

## 保守基线原则

本配置代表"Agent + 标准 CPG"的表示能力边界。当 CPG 证据不足以完整支撑某个确认条件时，**优先判 `no`**，不得靠架构常识、优先级嵌套推理、选择性屏蔽分析等 IACPG 方法论特有的推理来补全证据。

---

## 禁止行为

- **不得读取 `improved_interrupt_analysis/` 下的任何预处理产物**（Stage 1/2/3 产物一律禁止）。
- **不得读取任何 `*_backup*` 文件、`results/cpg_backups/` 目录或其他历史检测结果归档。**
- 不得调用 `interrupt_analyze`、`interrupt_analyze_merge`、`build_interrupt_facts`、`build_iacpg` 或任何 `iacpg_*` 工具。
- 不得凭源码阅读替代 CPG 查询证据；判定须有 `joern_*` 返回值支撑。
- 不得使用历史 `detection_result*`、`detection_report*`、`tool_call_log*`、`claude_run*.log` 来辅助当前判定。
- 不得删除、覆盖、重命名、移动或截断任何现有的 IACPG 结果文件（`detection_result.json`、`detection_report.md`、`tool_call_log.jsonl`、`claude_run_iacpg.log`）。
- 不得虚构工具返回字段。
- 不得只在聊天里给结论而不写入 `improved_interrupt_analysis`。
