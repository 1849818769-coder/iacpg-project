---
name: defect-detection
description: 面向混合缺陷数据集的嵌入式中断并发缺陷检测规范。必须走当前仓库真实链路：Stage 1 中断语义提取 → interrupt facts → IACPG → 图证据查询 → 四类缺陷并行判定，并把最终分析结果写回用例目录下的 improved_interrupt_analysis。
---

# 混合缺陷并行检测器

核心要求：
- 同一测试用例必须并行检查四类缺陷：`atomicity_violation`、`interrupt_aware_div_zero`、`interrupt_aware_array_oob`、`multiword_data_race`。
- 允许一个用例同时命中多个缺陷类型（多标签）。
- **最终结果必须落盘到 `<case>/improved_interrupt_analysis/`**，至少包含：
  - `detection_result.json`
  - `detection_report.md`
- 不得引用已删除的旧链路（如 `interrupt_model_build` / `interrupt_model_patch` / `interrupt_z3_verify`）。

### 源码阅读

- ✅ **允许**：读取源码以了解结构、核对行号、撰写报告。
- ❌ **禁止**：跳过 Stage 1/2/3 与 `iacpg_*` 图证据链，仅凭读源码直接判定缺陷（产物已存在时可跳过对应 Stage，仍须基于图证据下结论）。

## MCP 工具（server: `ice-interrupt-analyzer`）

### Stage 1（中断语义提取）
- `interrupt_analyze`
- `interrupt_analyze_merge`

### Stage 2（事实构建）
- `build_interrupt_facts`

### Stage 3（IACPG 构建）
- `build_iacpg`

### Stage 4（图证据查询）
- `iacpg_summary`
- `iacpg_preemptions`
- `iacpg_switches`
- `iacpg_variable`

### Joern 辅助（可选）
- `joern_import`
- `joern_workspace`
- `joern_methods`
- `joern_calls`
- `joern_identifiers`
- `joern_query`

---

## 总流程（必须执行）

1. **Stage 1 提取中断语义**
   - **跳过条件**：若 `<case>/improved_interrupt_analysis/functions.json` 已存在，跳过本阶段。
   - 已知架构（TestSuite / ARM / AVR / MSP430 / RISC-V）优先：
     - `interrupt_analyze(project_path=<path>, mode="static")`
   - 未知架构：
     - `interrupt_analyze(project_path=<path>, mode="agent")`
     - 再基于 `supplement_context` 构造 patch：
       - `interrupt_analyze_merge(project_path=<path>, agent_patch=<...>)`

2. **Stage 2 构建 interrupt facts**
   - **跳过条件**：若 `<case>/improved_interrupt_analysis/interrupt_facts/interrupt_facts.json` 已存在，跳过本阶段。
   - `build_interrupt_facts(project_path=<path>)`

3. **Stage 3 构建 IACPG**
   - **跳过条件**：若 `<case>/improved_interrupt_analysis/iacpg_artifacts/iacpg.graphml` 已存在，跳过本阶段。
   - `build_iacpg(project_path=<path>)`

4. **Stage 4 收集结构化证据**
   - 至少调用：
     - `iacpg_summary(project_path=<path>)`
     - `iacpg_preemptions(project_path=<path>)`
     - `iacpg_switches(project_path=<path>)`
   - 对每个共享变量候选调用：
     - `iacpg_variable(project_path=<path>, variable_name=<var>)`

5. **并行执行四类检查清单**
   - 原子性违反检查
   - 除零检查
   - 数组越界检查
   - 多字长数据竞争检查

6. **写回最终结果**
   - 将结构化结论写入：
     - `<case>/improved_interrupt_analysis/detection_result.json`
     - `<case>/improved_interrupt_analysis/detection_report.md`
   - 如果还有补充查询结果，可放在同目录下，但不得替代以上两个主结果文件。
   - 不得删除、覆盖、重命名或清空任何现有的 CPG 基线结果文件（如 `detection_result_cpg.json`、`detection_report_cpg.md`、`tool_call_log_cpg.jsonl`、`claude_run_cpg.log`）。

---

## Stage 1 关键约束（避免错误补全）

- `agent_patch.interrupt_functions[*].name` 必须与 `supplement_context.all_functions[*].name` 完全一致。
- `agent_patch.switch_targets[*].line` 必须与 `supplement_context.switch_operations[*].line` 完全一致。
- `targets` 只能填已归类为 interrupt 的函数。
- 未列出的函数自动归为 `regular`。

---

## 一等结构化证据（优先级最高）

- `INTERRUPT_PREEMPTS`
- `ENABLES` / `DISABLES`
- `ACCESSES_SHARED_VAR`
- `POTENTIAL_CONCURRENCY_ON`

说明：
- 图证据用于证明“可并发、可抢占、可影响”。
- 缺陷确认仍需类型特定汇点（例如二次读取、除法分母、数组索引访问）。

---

## 四类缺陷的典型特征与检查方法（并行执行）

> **公平性（与 CPG 基线对齐）**：下列各缺陷类型的「确认条件」序号条款为 **IACPG 与 CPG-only 共用的判定标准**；两配置仅 **证据形态** 不同（本配置以 `iacpg_*` 图证据为主；CPG 基线以 `joern_*` 查询结果支撑**同一套**条款），**不得**因工具不同而自行放宽或收紧条件。

### A. 原子性违反 `atomicity_violation`

**结论定义**：
- `yes` = 满足所有确认条件
- `no` = 缺少任何一个关键条件
- `uncertain` = 满足大部分条件，但无法100%确认（极少使用，优先给 no）

**确认条件（全部满足）**：
1. 至少两个中断相关上下文可交错（如 main/task 与 ISR）。
2. 访问同一共享状态（全局/静态变量、字段或等价逻辑状态）。
3. 至少一侧有写。
4. 主流程对共享状态存在**易受攻击的依赖模式**（满足以下任一即可）：
   a. `R-W-R`：主程序读 → ISR 写 → 主程序再次读同一共享变量。**两次读取本身就构成原子性违反模式**，不要求读取值被进一步使用——两次读取在并发窗口中可能得到不一致的值即为缺陷。包含：同一复合条件内多次引用（如 `(a < x) && (a > y)`）、不同 `if` 分支中分别读取、读入不同局部变量等。
   b. `W-W-R`：主程序写 → ISR 写不同值 → 主程序（或其调用函数）读取。读取本身即构成使用，不要求读取值被进一步计算。
   c. **check-then-use**：先检查共享状态，后基于检查结果执行依赖操作（check 与 use 之间存在可抢占窗口）。
   d. **同一表达式内多次使用**：同一共享变量在单个表达式内被多次引用。
   e. **读后依赖使用**：读取共享变量后，其值用于后续计算、赋值或分支判断。
   （仅当共享变量在主程序中只被访问恰好一次且该访问结果未被任何后续操作依赖时，才判 `no`。）
5. 脆弱窗口未被完整屏蔽保护（中断禁闭或等价临界区未覆盖该窗口）。

**典型强特征**：
- `R-W-R`：主程序读 → ISR 写 → 主程序再次读。
- `W-W-R`：主程序写 → ISR 写覆盖 → 主程序（或被调函数）读取。
- 条件读取与后续使用之间被 ISR 改写。
- 同一表达式/逻辑分支依赖共享状态一致性。
- 复合条件（如 `&&`、`||`、`?:`）中多次引用同一共享变量。

### B. 中断感知除零 `interrupt_aware_div_zero`

**结论定义**：
- `yes` = 满足所有确认条件
- `no` = 缺少任何一个关键条件
- `uncertain` = 满足大部分条件，但无法100%确认（极少使用，优先给 no）

**确认条件（全部满足）**：
1. 分母（或等效步长）来自共享状态。
2. 某处有非零检查或安全条件。
3. 检查与除法（或取模等以该量为除数/模数）之间存在可抢占窗口。
4. ISR 可将该共享状态改为 0 或导致无效除法的值。
5. 存在真实除法或取模汇点。

### C. 中断感知数组越界 `interrupt_aware_array_oob`

**结论定义**：
- `yes` = 满足所有确认条件
- `no` = 缺少任何一个关键条件
- `uncertain` = 满足大部分条件，但无法100%确认（极少使用，优先给 no）

**确认条件（全部满足）**：
1. 数组索引或界限由共享状态提供或派生。
2. 某处有边界检查或索引计算。
3. 检查与数组访问之间存在可抢占窗口。
4. ISR 可改变索引或驱动越界的共享状态。
5. 存在具体数组访问汇点（读或写）。

### D. 多字长数据竞争 `multiword_data_race`

**结论定义**：
- `yes` = 满足所有确认条件
- `no` = 缺少任何一个关键条件
- `uncertain` = 满足大部分条件，但无法100%确认（极少使用，优先给 no）

**确认条件（全部满足）**：
1. 变量是**多字长类型**（位宽 > 平台字宽），或存在多字配对变量（`_high` + `_low` 等模式）。
2. 变量被**主程序路径与 ISR 双方访问**（至少一方有写）。
3. 存在**可抢占窗口**：在缺乏同步保护时，主程序与 ISR 对相关访问可发生交错（**判定语义**与是否出现字面量图边名无关）。
4. 访问**未受锁或等效临界区保护**。

**证据要求（支撑第 3 条，不计入独立条件）**：优先使用图中 `INTERRUPT_PREEMPTS` 及相关边；若无，须用其它图查询结果**等价**说明可抢占。

**典型强特征**：
- 64 位变量在 32 位平台上：赋值/读写被拆分为多步骤。
- 多字配对：`sec_high` + `sec_low` 组合访问。
- 组装/拆分操作：`((high << 32) | low)` 非原子组合。

**与 atomicity_violation 的区别**：
- `atomicity_violation` 关注 **RMW（读-改-写）操作序列被中断分割**（软件层面）。
- `multiword_data_race` 关注 **单次访问跨越原子边界**（硬件层面）。

---

## 最终输出格式（必须）

### 1) 总结
- 测试用例：`<path-or-id>`
- 检测结论：`multi-label` / `single-label` / `no_bug` / `uncertain`
- 命中类型：`[atomicity_violation, interrupt_aware_div_zero, ...]`

### 2) 分类结果表（固定四行）

| 缺陷类型 | 结论 | 共享变量 | 三元窗口 (op1, interrupt, op3) | 关键证据 |
|---|---|---|---|---|
| atomicity_violation | yes/no | ... | (...) | ... |
| interrupt_aware_div_zero | yes/no | ... | (...) | ... |
| interrupt_aware_array_oob | yes/no | ... | (...) | ... |
| multiword_data_race | yes/no | ... | (...) | ... |

**结论定义**：
- `yes` = 满足所有确认条件，确认缺陷存在
- `no` = 缺少至少一个关键条件，缺陷不成立
- `uncertain` = （仅在极少数无法明确判断时使用，优先给 no）

要求：
- `关键证据` 至少包含一个图证据（边类型）+ 一个源码位置（或 `N/A` + 原因）。
- 若无法精确行号可写 `N/A`，但必须解释被拒绝的理由。

### 3) 落盘要求
- `detection_result.json`：**必须严格按照以下 JSON schema 输出，字段名不得修改**：

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

- `detection_report.md`：**必须严格按照以下 Markdown 模板输出，不得自行搜索其他用例作为参考**：

```markdown
# 缺陷检测报告

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

（对每个 conclusion=yes 的缺陷类型，列出图证据边 + 源码位置）

## 被拒绝候选与理由

（对每个 conclusion=no 的缺陷类型，说明缺少哪个确认条件）
```

---

## 对 CPG 结果的保护约束

- 不得删除、覆盖、重命名、移动或截断任何现有的 CPG 基线结果文件。
- 若同目录下已存在 `detection_result_cpg.json`、`detection_report_cpg.md`、`tool_call_log_cpg.jsonl`、`claude_run_cpg.log`，必须视为只读边界，不得修改。
- 若发现当前操作可能影响 CPG 结果文件，必须停止并只写 IACPG 自己的输出文件。

---

## ISR 行为推理约束

- **禁止追踪 ISR 内部条件分支来排除缺陷**：不得通过分析 ISR 内部的 flag/条件逻辑来论证"ISR 不会将变量设为危险值"。只要 ISR 代码中存在将共享变量设为危险值的赋值语句（如 `count = 0`），即视为"ISR 可将共享状态改为危险值"，不论该赋值是否受 ISR 内部条件保护。
- **理由**：ISR 内部条件可能依赖其他共享状态，这些状态本身可能被并发修改，静态分析无法可靠判定 ISR 内部分支的可达性。

---

## 禁止行为

- 不得跳过 Stage 1/2/3 直接凭源码印象下结论（除非对应产物文件已存在）。
- 不得虚构 MCP 工具返回字段。
- 不得把“存在并发边”直接当作“确认缺陷”。
- 不得继续引用旧的 Z3 三段式链路。
- 不得只在聊天里给结论而不写入 `improved_interrupt_analysis`。
- 不得删除、覆盖、重命名、移动或截断任何现有的 CPG 基线结果文件。
