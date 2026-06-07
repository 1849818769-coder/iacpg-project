/*
 * multiwordDatarace - simple_001
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

void init(void);
void idlerun(void);

volatile int64_t down_counter_ms = 0;

void simple_001_riscv_main(void) {
    __disable_irq();
    init();
    __enable_irq();
    down_counter_ms = 500;
    idlerun();
}

void MachineTimer_IRQHandler(void) {
    down_counter_ms = down_counter_ms - 1;
}
