# Hard Test Case Design Plan

## 设计目标

当前 64 个 easy 用例上 IACPG 和 CPG 都达到 F1=100%，无法体现 IACPG 的价值。
Hard 用例需要精确打击 CPG 的推理盲区，使 CPG 出现 FN（漏报）或 FP（误报），而 IACPG 仍能正确判定。

## CPG 的推理方式与能力边界

CPG-only 检测依赖三个核心推理步骤：

| 步骤 | CPG 做法 | 能力上限 |
|------|---------|---------|
| ISR 识别 | 函数名匹配 `*IRQHandler` / `ISR(*)` / `*_ISR` / `*_vect` | 只能识别符合命名规范的 ISR |
| 抢占判断 | 发现 `__enable_irq()` / `sei()` 调用 → 推断 main 可被中断 | 无法判断优先级嵌套、无法判断选择性屏蔽 |
| 保护判断 | 搜索 `__disable_irq()` / `cli()` 调用是否包围关键区 | 只能匹配已知 API 名、无法做路径敏感分析 |

## IACPG 的额外能力

| 能力 | IACPG 实现方式 |
|------|--------------|
| ISR 识别 | 规则 + LLM Agent 补全，CPG 节点存在性验证 |
| 优先级嵌套 | INTERRUPT_PREEMPTS 边，基于归一化优先级构建 |
| 选择性屏蔽 | ENABLES/DISABLES 边，精确到目标 IRQn |
| 保护范围 | GUARD 边 + 受保护属性标记，过程内 CFG 可达性分析 |
| 跨上下文共享 | ACCESSES_SHARED_VAR + POTENTIAL_CONCURRENCY_ON 边 |

## Hard 用例设计原则

每个 hard 用例**至少触及一个** CPG 盲区：

1. **部分屏蔽 (Selective Masking)**：`NVIC_DisableIRQ(TIM2_IRQn)` 屏蔽了低优先级 ISR，但高优先级 ISR 仍可抢占。CPG 看到 disable 调用就认为安全。
2. **间接共享 (Indirect Sharing)**：共享变量通过 helper 函数访问，CPG 的单层标识符搜索找不到跨上下文冲突。
3. **假保护 (Deceptive Guard)**：`__disable_irq()` 存在但不覆盖关键区域，或保护条件本身是共享变量。CPG 看到 disable 就误判为安全。
4. **非标准 ISR 命名**：ISR 函数名不符合已知模式，CPG 无法识别为中断处理函数。

---

## 具体用例设计

### AtomicityViolation/simple_005 — 选择性屏蔽 + 优先级嵌套

**CPG 盲区**：CPG 看到 `NVIC_DisableIRQ(TIM2_IRQn)` 包围关键区，判断为"已保护"→ 漏报。
**真实情况**：高优先级 ISR (USART1, priority=1) 未被屏蔽，仍可在关键区内抢占并修改共享变量。

```c
// ARM 版本骨架
typedef enum { TIM2_IRQn = 28, USART1_IRQn = 37 } IRQn_Type;

volatile int shared_counter;

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 3);    // 低优先级
    NVIC_SetPriority(USART1_IRQn, 1);  // 高优先级
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(USART1_IRQn);
    __enable_irq();

    // 看似安全：屏蔽了 TIM2
    NVIC_DisableIRQ(TIM2_IRQn);
    int tmp = shared_counter;        // R1
    tmp = tmp + 1;
    shared_counter = tmp;            // W1  ← USART1 可在 R1-W1 间抢占
    NVIC_EnableIRQ(TIM2_IRQn);
}

void TIM2_IRQHandler(void) {         // 被屏蔽 → 无法在关键区抢占
    shared_counter = 0;
}

void USART1_IRQHandler(void) {       // 未被屏蔽，高优先级 → 可抢占
    shared_counter = shared_counter + 10;  // W2
}
```

**IACPG 为何能检出**：
- INTERRUPT_PREEMPTS: main → USART1_IRQHandler (优先级 1 > 无)
- DISABLES 边只连接 TIM2_IRQHandler，不影响 USART1
- ACCESSES_SHARED_VAR: main(R+W) + USART1(R+W) on shared_counter
- 判定：R1-W1 窗口内 USART1 可抢占，构成 atomicity violation

**预期结果**：IACPG=TP, CPG=FN, ZeroShot=FN

---

### AtomicityViolation/simple_006 — 间接共享访问 (Helper 函数)

**CPG 盲区**：共享变量 `state` 在 main 中通过 `get_state()` / `set_state()` 间接读写。CPG 搜索 main 中的标识符不会直接看到 `state`，因此无法建立跨上下文共享。

```c
volatile int state;

static int get_state(void) { return state; }
static void set_state(int v) { state = v; }

void simple_006_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    int old = get_state();    // R (间接)
    int new_val = old + 1;
    set_state(new_val);       // W (间接)  ← ISR 可在 R-W 之间抢占
}

void TIM2_IRQHandler(void) {
    state = 0;                // W (直接)
}
```

**IACPG 为何能检出**：
- Stage 1 提取共享变量 `state`，追踪其在 get_state/set_state 中的访问
- ACCESSES_SHARED_VAR: main(通过调用链 R+W) + TIM2(W) on state
- INTERRUPT_PREEMPTS: main → TIM2_IRQHandler
- 判定：间接 R-W 窗口内 TIM2 可抢占

**预期结果**：IACPG=TP, CPG=FN, ZeroShot=可能TP（LLM 能理解函数语义）

---

### BufferOverflow/simple_005 — 假保护 (Guard 不覆盖关键区)

**CPG 盲区**：main 中存在 `__disable_irq()` 调用，但保护的是初始化段，不是数组访问段。CPG 看到 disable 存在 → 可能误判为"已保护"。

```c
#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int index_val;

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);

    // 保护的是初始化，不是后续访问
    __disable_irq();
    index_val = 0;
    __enable_irq();

    // 此处无保护！ISR 可在 check-use 之间修改 index_val
    if (index_val < BUFFER_SIZE) {
        buffer[index_val] = 42;   // ← OOB if ISR changes index_val
    }
}

void TIM2_IRQHandler(void) {
    index_val = BUFFER_SIZE + 5;  // 越界值
}
```

**IACPG 为何能检出**：
- GUARD 边：disable → enable 仅保护 `index_val = 0` 这一段
- 数组访问处的节点没有 `guarded=true` 属性
- POTENTIAL_CONCURRENCY_ON: index_val 在 check-use 窗口暴露

**预期结果**：IACPG=TP, CPG=FN（看到 disable 误判安全）

---

### BufferOverflow/simple_006 — 真阴性 (全局屏蔽保护)

**设计意图**：有 `__disable_irq()` 完整保护了 check-use 区间，无真实缺陷。测试 CPG 是否会因为找到共享变量+ISR 就误报。

```c
#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int idx;

void simple_006_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    __disable_irq();
    if (idx < BUFFER_SIZE) {
        buffer[idx] = 99;       // 安全：全局中断已关
    }
    __enable_irq();
}

void TIM2_IRQHandler(void) {
    idx = BUFFER_SIZE + 1;
}
```

**IACPG 判定**：GUARD 边覆盖 check-use 区间 → guarded=true → 无缺陷
**CPG 判定**：若 CPG 能识别 disable/enable 包围 → TN；若 CPG 仅检查共享变量 → FP

**预期结果**：IACPG=TN, CPG=TN 或 FP, ZeroShot=TN

**Ground Truth**：`defect_classes: []`

---

### DivideByZero/simple_005 — 间接除数 (函数返回值)

**CPG 盲区**：除数 `d` 来自 `get_divisor()` 函数返回值，而 `get_divisor()` 内部读取的是全局变量 `raw_divisor`。CPG 标识符搜索只在 main 中看到 `d`（局部变量），不会追踪到 `raw_divisor` 是跨上下文共享的。

```c
volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    raw_divisor = 10;
    int d = get_divisor();     // R: 读 raw_divisor（间接）
    if (d != 0) {
        int result = 100 / d;  // ← ISR 可在 get_divisor 和 if 之间改 raw_divisor
                               //    但 d 是局部快照...
                               //    真正风险：ISR 在 raw_divisor=10 赋值前抢占
    }
}

void TIM2_IRQHandler(void) {
    raw_divisor = 0;
}
```

等等，这里局部变量 `d` 是快照，ISR 改 `raw_divisor` 不影响已经读入的 `d`。让我重新设计，让风险真实存在：

```c
volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    raw_divisor = 10;
    // check: 直接检查全局
    if (raw_divisor != 0) {
        // use: 通过函数间接读取 → ISR 可在 check-use 间将其改为 0
        int d = get_divisor();
        int result = 100 / d;    // ← 除零风险
    }
}

void TIM2_IRQHandler(void) {
    raw_divisor = 0;
}
```

**IACPG 为何能检出**：
- ACCESSES_SHARED_VAR: main(R via get_divisor + R in check) + TIM2(W) on raw_divisor
- INTERRUPT_PREEMPTS: main → TIM2_IRQHandler
- check (raw_divisor != 0) 和 use (get_divisor() → raw_divisor) 之间有抢占窗口

**预期结果**：IACPG=TP, CPG=FN（不追踪 get_divisor 内部访问）

---

### DivideByZero/simple_006 — 保护条件本身是共享变量

**CPG 盲区**：main 中有条件 `if (safe_flag) { __disable_irq(); ... __enable_irq(); }`。CPG 看到 disable 调用存在 → 可能判断为安全。但 `safe_flag` 本身被 ISR 修改，保护可能不执行。

```c
volatile int divisor;
volatile int safe_flag;

void simple_006_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    divisor = 10;
    safe_flag = 1;

    // safe_flag 可被 ISR 改为 0 → 保护不执行
    if (safe_flag) {
        __disable_irq();
    }

    if (divisor != 0) {
        int r = 100 / divisor;   // ← 若 safe_flag 被改为 0，此处无保护
    }

    if (safe_flag) {
        __enable_irq();
    }
}

void TIM2_IRQHandler(void) {
    safe_flag = 0;               // 破坏保护条件
    divisor = 0;                 // 制造除零
}
```

**IACPG 为何能检出**：
- ACCESSES_SHARED_VAR: safe_flag 和 divisor 都是跨上下文共享
- GUARD 边分析：disable 在条件分支内，不能保证所有路径都受保护
- POTENTIAL_CONCURRENCY_ON: divisor 在 check-use 窗口暴露

**预期结果**：IACPG=TP, CPG=FN

---

### MultiwordDataRace/simple_005 — 非标准 ISR 命名

**CPG 盲区**：ISR 函数名为 `system_tick_callback`，不符合任何已知 ISR 命名模式。CPG 无法识别其为 ISR → 无法建立抢占关系 → 漏报。

```c
volatile int64_t timestamp;

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    int64_t snap = timestamp;     // 非原子读（64-bit on 32-bit ARM）
    if (snap > 0) {
        /* use snap */
    }
}

// ISR 用非标准名称，通过向量表注册
void system_tick_callback(void) {
    timestamp = timestamp + 1;    // 非原子写
}
```

**IACPG 为何能检出**：
- Stage 1 LLM Agent 识别 `system_tick_callback` 为 ISR（基于 NVIC_EnableIRQ 上下文 + 孤立入度模式）
- INTERRUPT_PREEMPTS: main → system_tick_callback
- ACCESSES_SHARED_VAR: 64-bit timestamp 非原子访问

**预期结果**：IACPG=TP, CPG=FN（命名不匹配）, ZeroShot=可能 FN

---

### MultiwordDataRace/simple_006 — 结构体多字段非原子访问

**CPG 盲区**：共享数据是结构体 `struct coord { int32_t x; int32_t y; }`，main 需要原子地读取 x 和 y（语义要求一致性），但分两次读取。CPG 类型检查只看单字段是 int32_t（原子），不理解结构体一致性语义。

```c
typedef struct {
    volatile int32_t x;
    volatile int32_t y;
} coord_t;

coord_t position;

void simple_006_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    // 需要一致性：x 和 y 应属于同一时刻的值
    int32_t px = position.x;    // R1
    int32_t py = position.y;    // R2  ← ISR 可在 R1-R2 间修改
    int32_t dist = px * px + py * py;
}

void TIM2_IRQHandler(void) {
    position.x = position.x + 1;
    position.y = position.y + 1;
}
```

**IACPG 为何能检出**：
- ACCESSES_SHARED_VAR: main(R on position.x, R on position.y) + TIM2(W on position.x, W on position.y)
- INTERRUPT_PREEMPTS: main → TIM2_IRQHandler
- R1-R2 之间存在抢占窗口，结构体字段一致性被破坏
- 判定：multiword data race（复合数据非原子访问）

**预期结果**：IACPG=TP, CPG=FN（每个字段都是 int32_t 原子，CPG 不检查结构体一致性）

---

## 总结表

| 用例 ID | 缺陷类型 | 难度策略 | CPG 盲区 | 预期 IACPG | 预期 CPG | 预期 ZS |
|---------|---------|---------|---------|-----------|---------|---------|
| AV/005 | AtomicityViolation | 选择性屏蔽+优先级嵌套 | 看到 disable 误判安全 | TP | **FN** | FN |
| AV/006 | AtomicityViolation | Helper 函数间接共享 | 标识符搜索不跨函数 | TP | **FN** | TP? |
| BO/005 | BufferOverflow | 假保护（不覆盖关键区） | 看到 disable 误判安全 | TP | **FN** | FN |
| BO/006 | BufferOverflow (TN) | 真保护 | — | TN | TN/FP | TN |
| DZ/005 | DivideByZero | 间接除数（函数返回值） | 不追踪函数内部访问 | TP | **FN** | FN |
| DZ/006 | DivideByZero | 保护条件是共享变量 | 看到 disable 误判安全 | TP | **FN** | FN |
| MDR/005 | MultiwordDataRace | 非标准 ISR 命名 | 命名模式不匹配 | TP | **FN** | FN |
| MDR/006 | MultiwordDataRace | 结构体一致性 | 单字段原子，不检查一致性 | TP | **FN** | FN |

**预期影响**：
- 新增 8 模板 × 4 架构 = 32 用例
- 总数据集：96 用例（92 TP + 4 TN → 扩展后 88 TP + 8 TN 或 92 TP + 4 TN 取决于 BO/006）
- CPG 预期 FN ≈ 7×4 = 28，F1 从 100% 降至约 ~76%
- IACPG 预期仍为 F1=100%
- 差距拉开：IACPG F1=100% vs CPG F1≈76% vs ZeroShot F1≈70%

## 跨架构适配要点

每个 hard 用例需要 4 个架构变体：

| 差异点 | ARM | AVR | MSP430 | RISC-V |
|--------|-----|-----|--------|--------|
| ISR 命名 | `*IRQHandler` | `ISR(*_vect)` | `__interrupt void *_ISR` | `*_IRQHandler` |
| 全局 enable | `__enable_irq()` | `sei()` | `__enable_interrupt()` | `__enable_irq()` |
| 全局 disable | `__disable_irq()` | `cli()` | `__disable_interrupt()` | `__disable_irq()` |
| 选择性 enable | `NVIC_EnableIRQ()` | 无（全局） | 无（全局） | `PLIC_EnableIRQ()` |
| 选择性 disable | `NVIC_DisableIRQ()` | 无（全局） | 无（全局） | `PLIC_DisableIRQ()` |
| 优先级设置 | `NVIC_SetPriority()` | 无 | 无 | `PLIC_SetPriority()` |
| 优先级嵌套 | 支持 | 不支持 | 不支持 | 支持 |

**注意**：AV/005（选择性屏蔽+优先级嵌套）仅适用于 ARM 和 RISC-V（AVR/MSP430 不支持选择性屏蔽）。AVR/MSP430 版本需要调整策略——改为"全局 disable 但嵌套中断仍可触发"的场景，或设计不同的难度点。
